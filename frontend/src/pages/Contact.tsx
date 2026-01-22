import Navigation from "@/components/Navigation";

const Contact = () => {
  return (
    <div className="min-h-screen">
      <Navigation />
      <section className="pt-32 pb-32 bg-background">
        <div className="container mx-auto px-6">
          <div className="max-w-7xl mx-auto">
            <div className="grid md:grid-cols-2 gap-20">
              <div>
                <h1 className="text-minimal text-muted-foreground mb-4">GET IN TOUCH</h1>
                <h2 className="text-4xl md:text-6xl font-light text-architectural mb-12">
                  Let's Create Something
                  <br />
                  Extraordinary
                </h2>
                
                <div className="space-y-8">
                  <div>
                    <h3 className="text-minimal text-muted-foreground mb-2">EMAIL</h3>
                    <a href="mailto:hello@archstudio.com" className="text-xl hover:text-muted-foreground transition-colors duration-300">
                      hello@archstudio.com
                    </a>
                  </div>
                  
                  <div>
                    <h3 className="text-minimal text-muted-foreground mb-2">PHONE</h3>
                    <a href="tel:+1234567890" className="text-xl hover:text-muted-foreground transition-colors duration-300">
                      +1 (234) 567-8900
                    </a>
                  </div>
                  
                  <div>
                    <h3 className="text-minimal text-muted-foreground mb-2">STUDIO</h3>
                    <address className="text-xl not-italic">
                      123 Design Avenue
                      <br />
                      New York, NY 10001
                    </address>
                  </div>
                </div>
              </div>
              
              <div className="space-y-8">
                <div>
                  <h3 className="text-minimal text-muted-foreground mb-6">FOLLOW US</h3>
                  <div className="space-y-4">
                    <a href="#" className="block text-xl hover:text-muted-foreground transition-colors duration-300">
                      Instagram
                    </a>
                    <a href="#" className="block text-xl hover:text-muted-foreground transition-colors duration-300">
                      LinkedIn
                    </a>
                    <a href="#" className="block text-xl hover:text-muted-foreground transition-colors duration-300">
                      Behance
                    </a>
                  </div>
                </div>
                
                <div className="pt-12 border-t border-border">
                  <p className="text-muted-foreground">
                    We approach each project with curiosity, rigor, and a commitment to excellence. 
                    Our process begins with listening, understanding your vision, and translating 
                    it into spaces that exceed expectations.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Contact;