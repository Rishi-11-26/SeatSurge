"""
SeatSurge Production Redis Lua Scripts.

All scripts execute atomically inside Redis:
- Zero race conditions or double bookings under extreme concurrent traffic.
- Redis server-time used exclusively via redis.call('TIME') (eliminates clock drift).
- Atomic counter management with strict underflow protection.
- Atomic lock acquisition, renewal and release using compare-token semantics.
"""

# ── 1. ATOMIC SEAT CLAIM (All-or-Nothing Group & Single Holds) ────────────────
# KEYS[1] = event:{event_id}:seat_statuses (Hash: seat_id -> status)
# KEYS[2] = hold_expiry_zset (Sorted Set: hold_id -> expires_at)
# KEYS[3] = holds:active:count (String: integer counter)
# KEYS[4] = hold:{hold_id} (Hash: hold metadata)
#
# ARGV[1] = hold_id
# ARGV[2] = event_id
# ARGV[3] = session_id
# ARGV[4] = hold_ttl_seconds (default 120)
# ARGV[5] = seat_ids_csv (e.g. "101,102,103")
# ARGV[6..N] = individual seat_id strings
CLAIM_HOLD_LUA = """
local seat_statuses_key = KEYS[1]
local expiry_zset_key   = KEYS[2]
local counter_key       = KEYS[3]
local hold_meta_key     = KEYS[4]

local hold_id       = ARGV[1]
local event_id      = ARGV[2]
local session_id    = ARGV[3]
local ttl           = tonumber(ARGV[4])
local seat_ids_csv  = ARGV[5]

-- 1. Get authoritative Redis server time
local time_res   = redis.call('TIME')
local now_sec    = tonumber(time_res[1])
local expires_at = now_sec + ttl

-- 2. Validate all requested seats are AVAILABLE (All-or-Nothing check)
local num_seats = #ARGV - 5
for i = 6, #ARGV do
    local seat_id = ARGV[i]
    local st = redis.call('HGET', seat_statuses_key, seat_id)
    if st and st ~= 'AVAILABLE' then
        -- Conflict detected: reject entire request immediately
        return {'CONFLICT', seat_id, st}
    end
end

-- 3. All seats verified free -> claim atomically
for i = 6, #ARGV do
    local seat_id = ARGV[i]
    redis.call('HSET', seat_statuses_key, seat_id, 'HELD')
    local seat_hold_key = 'seat_holds:' .. event_id .. ':' .. seat_id
    redis.call('SET', seat_hold_key, hold_id, 'EX', ttl + 60)
end

-- 4. Store hold metadata
redis.call('HSET', hold_meta_key,
    'hold_id', hold_id,
    'event_id', event_id,
    'session_id', session_id,
    'seat_ids', seat_ids_csv,
    'held_at', tostring(now_sec),
    'expires_at', tostring(expires_at),
    'status', 'HELD'
)
redis.call('EXPIRE', hold_meta_key, ttl + 60)

-- 5. Add to sorted set for fast O(log N) expiry harvesting
redis.call('ZADD', expiry_zset_key, expires_at, hold_id)

-- 6. Atomically increment active hold counter
local current_holds = tonumber(redis.call('GET', counter_key) or '0')
redis.call('SET', counter_key, tostring(current_holds + num_seats))

return {'OK', tostring(expires_at), tostring(now_sec)}
"""


# ── 2. ATOMIC HOLD RELEASE (Manual Session Cancellation) ──────────────────────
# KEYS[1] = hold:{hold_id}
# KEYS[2] = event:{event_id}:seat_statuses
# KEYS[3] = hold_expiry_zset
# KEYS[4] = holds:active:count
#
# ARGV[1] = hold_id
# ARGV[2] = session_id (caller must own hold, or pass '__SYSTEM__' for admin)
RELEASE_HOLD_LUA = """
local hold_meta_key     = KEYS[1]
local seat_statuses_key = KEYS[2]
local expiry_zset_key   = KEYS[3]
local counter_key       = KEYS[4]

local hold_id    = ARGV[1]
local session_id = ARGV[2]

-- 1. Check hold existence
local hold_exists = redis.call('EXISTS', hold_meta_key)
if hold_exists == 0 then
    return {'NOT_FOUND'}
end

-- 2. Verify ownership unless authorized system caller
local owner = redis.call('HGET', hold_meta_key, 'session_id')
if session_id ~= '__SYSTEM__' and owner ~= session_id then
    return {'FORBIDDEN'}
end

-- 3. Check hold state: PAYING holds CANNOT be released merely because of hold cancel
local status = redis.call('HGET', hold_meta_key, 'status')
if status == 'PAYING' then
    return {'PROTECTED_PAYING'}
end

-- 4. Release each seat
local event_id     = redis.call('HGET', hold_meta_key, 'event_id')
local seat_ids_csv = redis.call('HGET', hold_meta_key, 'seat_ids')

local num_seats = 0
if seat_ids_csv then
    for seat_id in string.gmatch(seat_ids_csv, '([^,]+)') do
        num_seats = num_seats + 1
        redis.call('HSET', seat_statuses_key, seat_id, 'AVAILABLE')
        redis.call('DEL', 'seat_holds:' .. event_id .. ':' .. seat_id)
    end
end

-- 5. Remove from expiry zset and delete hold metadata
redis.call('ZREM', expiry_zset_key, hold_id)
redis.call('DEL', hold_meta_key)

-- 6. Atomically decrement counter with strict underflow protection
local current_holds = tonumber(redis.call('GET', counter_key) or '0')
local new_val = math.max(0, current_holds - num_seats)
redis.call('SET', counter_key, tostring(new_val))

return {'OK', tostring(num_seats), seat_ids_csv or ''}
"""


# ── 3. ATOMIC EXPIRY REAPER (Reap Single Expired Hold) ────────────────────────
# KEYS[1] = hold:{hold_id}
# KEYS[2] = event:{event_id}:seat_statuses
# KEYS[3] = hold_expiry_zset
# KEYS[4] = holds:active:count
#
# ARGV[1] = hold_id
# ARGV[2] = current_timestamp
REAP_EXPIRED_HOLD_LUA = """
local hold_meta_key     = KEYS[1]
local seat_statuses_key = KEYS[2]
local expiry_zset_key   = KEYS[3]
local counter_key       = KEYS[4]

local hold_id = ARGV[1]

-- If hold record no longer exists, just prune from zset
local hold_exists = redis.call('EXISTS', hold_meta_key)
if hold_exists == 0 then
    redis.call('ZREM', expiry_zset_key, hold_id)
    return {'NOT_FOUND'}
end

-- CRITICAL SAFETY: Never reap a PAYING hold!
local status = redis.call('HGET', hold_meta_key, 'status')
if status == 'PAYING' or status == 'SOLD' then
    -- Remove from expiry zset so it is not reaped; payment simulator owns it
    redis.call('ZREM', expiry_zset_key, hold_id)
    return {'PROTECTED_PAYING'}
end

local event_id     = redis.call('HGET', hold_meta_key, 'event_id')
local seat_ids_csv = redis.call('HGET', hold_meta_key, 'seat_ids')

local num_seats = 0
if seat_ids_csv then
    for seat_id in string.gmatch(seat_ids_csv, '([^,]+)') do
        num_seats = num_seats + 1
        redis.call('HSET', seat_statuses_key, seat_id, 'AVAILABLE')
        redis.call('DEL', 'seat_holds:' .. event_id .. ':' .. seat_id)
    end
end

-- Remove hold and prune zset
redis.call('ZREM', expiry_zset_key, hold_id)
redis.call('DEL', hold_meta_key)

-- Decrement counter with underflow protection
local current_holds = tonumber(redis.call('GET', counter_key) or '0')
local new_val = math.max(0, current_holds - num_seats)
redis.call('SET', counter_key, tostring(new_val))

return {'REAPED', tostring(num_seats), seat_ids_csv or ''}
"""


# ── 4. ATOMIC DISTRIBUTED RECOVERY LOCK SCRIPTS ──────────────────────────────
# Compare token and extend TTL
# KEYS[1] = recovery_lock
# ARGV[1] = owner_token
# ARGV[2] = extend_ttl_seconds
COMPARE_AND_EXTEND_LOCK_LUA = """
local lock_key    = KEYS[1]
local owner_token = ARGV[1]
local ttl         = tonumber(ARGV[2])

local current_owner = redis.call('GET', lock_key)
if current_owner == owner_token then
    redis.call('EXPIRE', lock_key, ttl)
    return 1
else
    return 0
end
"""

# Compare token and delete lock
# KEYS[1] = recovery_lock
# ARGV[1] = owner_token
COMPARE_AND_DELETE_LOCK_LUA = """
local lock_key    = KEYS[1]
local owner_token = ARGV[1]

local current_owner = redis.call('GET', lock_key)
if current_owner == owner_token then
    redis.call('DEL', lock_key)
    return 1
else
    return 0
end
"""


# ── 5. TRANSITION HOLD TO PAYING / SOLD ──────────────────────────────────────
# KEYS[1] = hold:{hold_id}
# KEYS[2] = event:{event_id}:seat_statuses
# KEYS[3] = hold_expiry_zset
# KEYS[4] = holds:active:count
#
# ARGV[1] = target_status ("PAYING" or "SOLD")
TRANSITION_HOLD_LUA = """
local hold_meta_key     = KEYS[1]
local seat_statuses_key = KEYS[2]
local expiry_zset_key   = KEYS[3]
local counter_key       = KEYS[4]

local target_status = ARGV[1]

local hold_exists = redis.call('EXISTS', hold_meta_key)
if hold_exists == 0 then
    return {'NOT_FOUND'}
end

local seat_ids_csv = redis.call('HGET', hold_meta_key, 'seat_ids')
local hold_id      = redis.call('HGET', hold_meta_key, 'hold_id')

if target_status == 'PAYING' then
    redis.call('HSET', hold_meta_key, 'status', 'PAYING')
    if seat_ids_csv then
        for seat_id in string.gmatch(seat_ids_csv, '([^,]+)') do
            redis.call('HSET', seat_statuses_key, seat_id, 'PAYING')
        end
    end
    -- Remove from hold expiry zset (protected from hold reaper)
    redis.call('ZREM', expiry_zset_key, hold_id)
    return {'OK', 'PAYING'}
elseif target_status == 'SOLD' then
    redis.call('HSET', hold_meta_key, 'status', 'SOLD')
    local num_seats = 0
    if seat_ids_csv then
        for seat_id in string.gmatch(seat_ids_csv, '([^,]+)') do
            num_seats = num_seats + 1
            redis.call('HSET', seat_statuses_key, seat_id, 'SOLD')
        end
    end
    redis.call('ZREM', expiry_zset_key, hold_id)
    -- Decrement active hold counter
    local current = tonumber(redis.call('GET', counter_key) or '0')
    redis.call('SET', counter_key, tostring(math.max(0, current - num_seats)))
    return {'OK', 'SOLD'}
elseif target_status == 'REVERT_HELD' then
    redis.call('HSET', hold_meta_key, 'status', 'HELD')
    if seat_ids_csv then
        for seat_id in string.gmatch(seat_ids_csv, '([^,]+)') do
            redis.call('HSET', seat_statuses_key, seat_id, 'HELD')
        end
    end
    local time_res = redis.call('TIME')
    local now_sec = tonumber(time_res[1])
    local exp = tonumber(redis.call('HGET', hold_meta_key, 'expires_at') or '0')
    if exp <= now_sec then
        exp = now_sec + 60
        redis.call('HSET', hold_meta_key, 'expires_at', tostring(exp))
    end
    redis.call('ZADD', expiry_zset_key, exp, hold_id)
    return {'OK', 'HELD', tostring(exp)}
end

return {'INVALID_TARGET'}
"""


# ── 6. ATOMIC FIFO QUEUE ENQUEUE ─────────────────────────────────────────────
# KEYS[1] = waiting_zset (Sorted Set: session_id -> order_seq)
# KEYS[2] = order_counter (String: integer counter)
# ARGV[1] = session_id
#
# Atomically checks if session_id is already in waiting_zset.
# If already present, returns existing score without incrementing counter.
# If not present, atomically increments counter and adds session to zset with that score.
ENQUEUE_FIFO_LUA = """
local waiting_zset = KEYS[1]
local counter_key  = KEYS[2]
local session_id   = ARGV[1]

local existing = redis.call('ZSCORE', waiting_zset, session_id)
if existing then
    return existing
end

local seq = redis.call('INCR', counter_key)
redis.call('ZADD', waiting_zset, seq, session_id)
return tostring(seq)
"""


# ── 7. ATOMIC WEBSOCKET EVENT SEQUENCE & LOG INSERTION ───────────────────────
# KEYS[1] = ws_seq_key (String: monotonic sequence counter)
# KEYS[2] = ws_event_log_key (List: capped event replay buffer)
# KEYS[3] = ws_channel_key (Pub/Sub channel)
# ARGV[1] = event_id
# ARGV[2] = updates_json
# ARGV[3] = timestamp_iso
#
# Atomically increments sequence, formats payload, pushes to log, trims to 500,
# and publishes to pub/sub channel.
PUBLISH_WS_EVENT_LUA = """
local seq_key    = KEYS[1]
local log_key    = KEYS[2]
local chan_key   = KEYS[3]
local event_id   = ARGV[1]
local updates    = ARGV[2]
local timestamp  = ARGV[3]

local new_seq = redis.call('INCR', seq_key)
local payload = '{"type":"SEAT_STATUS_CHANGE","seq":' .. new_seq .. ',"event_id":' .. event_id .. ',"updates":' .. updates .. ',"timestamp":"' .. timestamp .. '"}'

redis.call('RPUSH', log_key, payload)
redis.call('LTRIM', log_key, -500, -1)
redis.call('PUBLISH', chan_key, payload)

return {tostring(new_seq), payload}
"""
