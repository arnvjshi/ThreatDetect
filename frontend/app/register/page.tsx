import { Metadata } from 'next';
import type { JSX } from 'react';
import RegistrationForm from '@/components/RegistrationForm';

export const metadata: Metadata = {
  title: 'Register User - ThreatDetect',
  description: 'Register your email to receive threat alerts',
};

export default function RegistrationPage(): Readonly<JSX.Element> {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-gradient-to-br from-[#05070b] to-[#0f172a] px-4">
      <div className="w-full max-w-md">
        <RegistrationForm />
      </div>
    </div>
  );
}
