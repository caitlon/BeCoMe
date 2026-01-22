import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";

const Navigation = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
      <div className="container mx-auto px-6 py-4 flex items-center justify-between">
        <div className="text-minimal text-foreground">
          ARCH STUDIO
        </div>
        
        <div className="hidden md:flex items-center space-x-12">
          <a href="/work" className="text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
            WORK
          </a>
          <a href="/services" className="text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
            SERVICES
          </a>
          <a href="/about" className="text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
            ABOUT
          </a>
          <a href="/blog" className="text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
            BLOG
          </a>
          <a href="/contact" className="text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
            CONTACT
          </a>
        </div>

        <div className="hidden md:flex items-center space-x-4">
          <ThemeToggle />
        </div>

        <Button
          variant="ghost"
          size="sm"
          className="md:hidden"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
        >
          {isMenuOpen ? '✕' : '☰'}
        </Button>
      </div>

      {/* Mobile Menu */}
      {isMenuOpen && (
        <div className="md:hidden bg-background border-b border-border">
          <div className="container mx-auto px-6 py-6 space-y-4">
            <a href="/work" className="block text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
              WORK
            </a>
            <a href="/services" className="block text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
              SERVICES
            </a>
            <a href="/about" className="block text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
              ABOUT
            </a>
            <a href="/blog" className="block text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
              BLOG
            </a>
            <a href="/contact" className="block text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300">
              CONTACT
            </a>
            
            {/* Mobile Theme Toggle */}
            <div className="pt-4 border-t border-border">
              <ThemeToggle />
            </div>
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navigation;