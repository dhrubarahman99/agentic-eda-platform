import Navbar from '@/components/landing/Navbar'
import HeroSection from '@/components/landing/HeroSection'
import FeaturesSection from '@/components/landing/FeaturesSection'
import HowItWorksSection from '@/components/landing/HowItWorksSection'
import MLSection from '@/components/landing/MLSection'
import ComparisonSection from '@/components/landing/ComparisonSection'
import CTASection from '@/components/landing/CTASection'
import Footer from '@/components/landing/Footer'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <Navbar />
      <HeroSection />
      <FeaturesSection />
      <HowItWorksSection />
      <MLSection />
      <ComparisonSection />
      <CTASection />
      <Footer />
    </div>
  )
}
