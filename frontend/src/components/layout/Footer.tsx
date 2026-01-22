import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-border bg-card">
      <div className="container mx-auto px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Logo & Description */}
          <div className="md:col-span-2">
            <Link to="/" className="font-display text-xl font-medium">
              BeCoMe
            </Link>
            <p className="mt-3 text-sm text-muted-foreground max-w-md">
              Best Compromise Mean — a scientific approach to aggregating expert 
              opinions using fuzzy triangular numbers.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="font-medium text-sm mb-4">Product</h4>
            <ul className="space-y-2">
              <li>
                <Link to="/register" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                  Get Started
                </Link>
              </li>
              <li>
                <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                  Sign In
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-medium text-sm mb-4">Research</h4>
            <ul className="space-y-2">
              <li>
                <span className="text-sm text-muted-foreground">
                  VSB-TU Ostrava
                </span>
              </li>
              <li>
                <span className="text-sm text-muted-foreground">
                  Faculty of Economics
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-border flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} BeCoMe. All rights reserved.
          </p>
          <p className="text-sm text-muted-foreground">
            Research project by VSB-Technical University of Ostrava
          </p>
        </div>
      </div>
    </footer>
  );
}
