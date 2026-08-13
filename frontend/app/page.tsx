import { Background } from "@/components/Background";
import HeroSection from "@/components/HeroSection";
import Navbar from "@/components/Navbar";

export default function Home() {
  return (
    <div className="relative flex min-h-screen flex-col">
      <Background variant="hero" />
      <Navbar />
      <HeroSection />
    </div>
  );
}
