import React from 'react';
import { ShieldCheck, Lock, CreditCard } from 'lucide-react';

export default function CheckoutPlaceholder({ onNavigate }) {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-6">
      <div className="w-16 h-16 mx-auto rounded-full bg-[#EAE3D6] border border-[#D8CEBF] flex items-center justify-center text-[#C8962A]">
        <ShieldCheck className="w-8 h-8" />
      </div>
      <div>
        <span className="text-xs font-mono uppercase tracking-widest text-[#C8962A] font-semibold">
          PHASE F4 SCAFFOLD
        </span>
        <h2 className="font-editorial text-3xl font-bold text-[#15130F] mt-1">
          Hold-and-Pay Checkout & Idempotency
        </h2>
        <p className="text-sm text-[#4A453D] max-w-md mx-auto mt-2">
          Strict 2-minute hold timer, idempotent payment keys, handling payment failures and duplicate charge prevention.
        </p>
      </div>

      <div className="bg-[#EAE3D6] border border-[#D8CEBF] rounded-lg p-6 max-w-md mx-auto text-left space-y-3 font-mono text-xs">
        <div className="flex justify-between border-b border-[#D8CEBF] pb-2">
          <span className="text-[#706A61]">IDEMPOTENCY:</span>
          <span className="font-bold text-[#3F6B4F]">CLIENT UNIQUE UUID HEADER</span>
        </div>
        <div className="flex justify-between border-b border-[#D8CEBF] pb-2">
          <span className="text-[#706A61]">PAYMENT RETRIES:</span>
          <span>ZERO DUPLICATE CHARGES</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[#706A61]">AUTHORITY:</span>
          <span>BACKEND STRICT VERIFICATION</span>
        </div>
      </div>

      <div className="pt-4 flex justify-center gap-4">
        <button
          onClick={() => onNavigate('landing')}
          className="px-5 py-2.5 bg-[#15130F] text-[#F4EFE6] rounded text-xs font-medium hover:bg-[#2A2620]"
        >
          Back to Event Overview
        </button>
      </div>
    </div>
  );
}
