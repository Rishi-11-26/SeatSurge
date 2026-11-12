/**
 * SeatSurge Event Service Layer
 * 
 * DATA CLASSIFICATION:
 * 1. BACKEND-AUTHORITATIVE DATA:
 *    - Event ID: 1
 *    - Total Seats: 5,040
 *    - Tiers: VIP, PREMIUM, STANDARD
 *    - Row ranges: VIP (A-D), PREMIUM (E-P), STANDARD (Q-Z, AA-AH)
 *    - Seat counts: VIP (240), PREMIUM (1,200), STANDARD (3,600)
 *    - Raw prices: VIP (15,000 cents), PREMIUM (10,000 cents), STANDARD (5,000 cents)
 *    - Sections: "Floor VIP" (VIP), "Lower Bowl" (PREMIUM), "Upper Bowl" (STANDARD)
 *    - Max Group Size: 6 adjacent seats
 *    - Hold TTL: 120 seconds
 * 
 * 2. STATIC ILLUSTRATIVE CONTENT:
 *    - Headline title, artist narrative, schedule timetable, arena entry guidelines.
 * 
 * 3. DEVELOPMENT MOCK DATA:
 *    - Secondary catalog events (ICC T20, A.R. Rahman) used for discovery prototyping.
 */

export const PRIMARY_EVENT = {
  id: 1, // Authoritative Event ID
  title: "Coldplay: Music of the Spheres — World Tour Finale",
  shortTitle: "Coldplay Tour Finale",
  headline: "Live from Surge Arena, Motera (5,040 Capacity Showcase)",
  category: "Concert",
  genre: "Alternative Rock / Stadium Pop",
  dateIso: "2026-11-28",
  dateFormatted: "Saturday, November 28, 2026",
  time: "19:30 IST",
  doorsOpen: "17:00 IST",
  status: "FLASH_SALE_ACTIVE",
  
  // Authoritative Venue Metrics
  venue: {
    name: "Surge Arena, Motera",
    city: "Ahmedabad, India",
    totalSeats: 5040, // Authoritative
    address: "Stadium Rd, Motera, Ahmedabad, Gujarat 380005",
    gates: "Gates 1 to 8 (North & South Plazas)",
    transit: "Metro Line 1 (Motera Stadium Station - 200m)",
    parking: "Designated Park & Ride with Shuttle Access"
  },

  // Authoritative Business Rules (from backend config & api-contract.md)
  businessRules: {
    totalSeats: 5040,
    holdDurationSeconds: 120,
    maxGroupSeats: 6,
    seatStates: ["AVAILABLE", "HELD", "PAYING", "SOLD", "RELEASED"]
  },

  // Authoritative Tier Allocations (Matches Backend init_db.py exactly)
  tiers: [
    {
      id: "VIP",
      name: "Floor VIP",
      tier: "VIP", // Authoritative
      section: "Floor VIP",
      rows: "Rows A – D", // Authoritative (4 rows)
      seatsCount: 240, // Authoritative: 4 rows × 60 seats/row = 240
      seatIdRange: [1, 240], // Authoritative IDs: 1 to 240
      seatsPerRow: 60,
      priceCents: 15000, // Authoritative integer cents from api-contract.md & init_db.py
      priceFormatted: "₹ 150.00", // Formatted rupee equivalent (15,000 cents / 100)
      accentColor: "#E8472B",
      bgBadge: "bg-[#E8472B]/10 text-[#E8472B] border-[#E8472B]/30",
      description: "Rows A to D directly facing the main stage runway. Maximum proximity with fast-track Gate 1 access.",
      perks: [
        "Unobstructed center sightline (< 20m from main runway)",
        "Dedicated VIP Fast-Track Entry (Gate 1)",
        "Complimentary tour programme & physical lanyard",
        "Exclusive climate-controlled hospitality concourse"
      ]
    },
    {
      id: "PREMIUM",
      name: "Lower Bowl",
      tier: "PREMIUM", // Authoritative
      section: "Lower Bowl",
      rows: "Rows E – P", // Authoritative (12 rows)
      seatsCount: 1200, // Authoritative: 12 rows × 100 seats/row = 1,200
      seatIdRange: [241, 1440], // Authoritative IDs: 241 to 1,440
      seatsPerRow: 100,
      priceCents: 10000, // Authoritative integer cents (10,000 cents)
      priceFormatted: "₹ 100.00", // Formatted rupee equivalent (10,000 cents / 100)
      accentColor: "#C8962A",
      bgBadge: "bg-[#C8962A]/10 text-[#C8962A] border-[#C8962A]/30",
      description: "Rows E to P offering elevated 30-degree bowl sightlines, padded club seating, and rapid concessions.",
      perks: [
        "Elevated 30-degree panoramic stadium vantage",
        "Padded ergonomic stadium club seating",
        "Express food and beverage concession lanes",
        "Convenient mid-tier concourse exit gates"
      ]
    },
    {
      id: "STANDARD",
      name: "Upper Bowl",
      tier: "STANDARD", // Authoritative
      section: "Upper Bowl",
      rows: "Rows Q – Z & AA – AH", // Authoritative (18 rows: 10 + 8)
      seatsCount: 3600, // Authoritative: 18 rows × 200 seats/row = 3,600
      seatIdRange: [1441, 5040], // Authoritative IDs: 1,441 to 5,040
      seatsPerRow: 200,
      priceCents: 5000, // Authoritative integer cents (5,000 cents)
      priceFormatted: "₹ 50.00", // Formatted rupee equivalent (5,000 cents / 100)
      accentColor: "#3F6B4F",
      bgBadge: "bg-[#3F6B4F]/10 text-[#3F6B4F] border-[#3F6B4F]/30",
      description: "Rows Q to Z and AA to AH spanning the expansive upper deck. High-energy stadium acoustics.",
      perks: [
        "Full stadium bowl overview and synchronized light shows",
        "Optimized delay-tower acoustic dispersion",
        "High-energy general audience atmosphere",
        "Direct access to outer concourses & metro shuttles"
      ]
    }
  ],

  // Static Illustrative Schedule (Editorial Content)
  lineup: [
    { time: "17:00", act: "Gates & Concourse Open", stage: "Plaza Security" },
    { time: "18:00", act: "Resident DJ Soundcheck Set", stage: "Main Stage" },
    { time: "18:45", act: "Special Guest Opening Performance", stage: "Main Stage" },
    { time: "19:30", act: "Coldplay — Music of the Spheres Tour Set", stage: "Main & B-Stage" },
    { time: "21:30", act: "Synchronized Eco-Pyrotechnic Finale", stage: "Arena Sky" }
  ],

  // Static Illustrative Venue Policies (Editorial Content)
  policies: [
    { title: "Zero Double Bookings", desc: "Every held seat is guarded by atomic Redis single-transaction Lua locks." },
    { title: "120-Second Hold Window", desc: "Strict 2-minute hold timer enforced by the background expiration reaper." },
    { title: "Max 6 Adjacent Seats", desc: "Group bookings are strictly capped at 6 continuous seats per transaction." },
    { title: "Dynamic QR Ingress", desc: "Digital verifiable passes issued immediately upon backend payment confirmation." }
  ]
};

/**
 * DEVELOPMENT MOCK DATA: Secondary discovery events
 */
export const DISCOVERY_EVENTS = [
  PRIMARY_EVENT,
  {
    id: 2,
    title: "ICC T20 Championship 2026: Grand Finale",
    shortTitle: "ICC T20 Final",
    headline: "India vs Australia — World Cup Showdown",
    category: "Sports",
    genre: "Cricket / International T20",
    dateIso: "2026-12-06",
    dateFormatted: "Sunday, December 6, 2026",
    time: "19:00 IST",
    status: "COMING_SOON",
    isMock: true,
    venue: {
      name: "Surge Arena, Motera",
      city: "Ahmedabad, India",
      totalSeats: 5040
    },
    priceRange: "5,000¢ – 25,000¢ (₹50 – ₹250)",
    totalSeats: 5040
  },
  {
    id: 3,
    title: "A.R. Rahman: Symphony of Harmony Live",
    shortTitle: "A.R. Rahman Live",
    headline: "Complete 100-Piece Orchestra & Choir",
    category: "Concert",
    genre: "Orchestral / World Cinema",
    dateIso: "2026-12-19",
    dateFormatted: "Saturday, December 19, 2026",
    time: "18:30 IST",
    status: "COMING_SOON",
    isMock: true,
    venue: {
      name: "Surge Arena, Motera",
      city: "Ahmedabad, India",
      totalSeats: 5040
    },
    priceRange: "4,000¢ – 18,000¢ (₹40 – ₹180)",
    totalSeats: 5040
  },
  {
    id: 4,
    title: "Royal Philharmonic Orchestra: Mahler's Fifth",
    shortTitle: "Mahler's Fifth",
    headline: "Conducted by Sir Simon Rattle",
    category: "Theatre",
    genre: "Classical / Orchestral",
    dateIso: "2027-01-15",
    dateFormatted: "Friday, January 15, 2027",
    time: "20:00 IST",
    status: "UPCOMING",
    isMock: true,
    venue: {
      name: "Surge Hall of Symphony",
      city: "Mumbai, India",
      totalSeats: 2500
    },
    priceRange: "6,000¢ – 22,000¢ (₹60 – ₹220)",
    totalSeats: 2500
  }
];

export function getEventById(id) {
  const numericId = Number(id);
  return DISCOVERY_EVENTS.find(e => e.id === numericId) || PRIMARY_EVENT;
}
