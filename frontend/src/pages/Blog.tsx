import { useState } from "react";
import { Link } from "react-router-dom";
import Navigation from "@/components/Navigation";
import { blogPosts } from "@/data/blogPosts";

const Blog = () => {
  const [activeCategory, setActiveCategory] = useState("ALL");
  
  const categories = ["ALL", "SUSTAINABILITY", "DESIGN", "URBAN PLANNING"];
  
  const filteredPosts = activeCategory === "ALL" 
    ? blogPosts 
    : blogPosts.filter(post => post.category === activeCategory);

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      {/* Hero Section */}
      <section className="pt-32 pb-20">
        <div className="container mx-auto px-6">
          <div className="max-w-7xl mx-auto">
            <div className="mb-12">
              <h1 className="text-6xl md:text-8xl font-light text-architectural mb-8">
                INSIGHTS
              </h1>
              <p className="text-xl text-muted-foreground max-w-3xl">
                Exploring the intersection of architecture, design, and human experience 
                through thoughtful analysis and contemporary perspectives.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Filter Categories */}
      <section className="pb-16">
        <div className="container mx-auto px-6">
          <div className="max-w-7xl mx-auto">
            <div className="flex flex-wrap gap-8 justify-center md:justify-start">
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setActiveCategory(category)}
                  className={`text-minimal transition-colors duration-300 relative group ${
                    activeCategory === category 
                      ? "text-foreground" 
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {category}
                  <span className={`absolute bottom-0 left-0 w-full h-px bg-foreground transition-transform duration-300 origin-left ${
                    activeCategory === category 
                      ? "scale-x-100" 
                      : "scale-x-0 group-hover:scale-x-100"
                  }`}></span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Blog Posts Grid */}
      <section className="pb-32">
        <div className="container mx-auto px-6">
          <div className="max-w-7xl mx-auto">
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-12 lg:gap-16">
              {filteredPosts.map((post) => (
                <article key={post.id} className="group">
                  <Link to={`/blog/${post.id}`} className="block">
                    <div className="relative overflow-hidden mb-6">
                      <img 
                        src={post.image} 
                        alt={post.title}
                        className="w-full h-64 object-cover transition-transform duration-700 group-hover:scale-105"
                      />
                      <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                      
                      {/* Category Badge */}
                      <div className="absolute top-4 left-4 bg-background/90 backdrop-blur-sm px-3 py-1">
                        <span className="text-xs text-foreground font-medium">
                          {post.category}
                        </span>
                      </div>
                    </div>
                    
                    <div className="space-y-4">
                      <div className="flex items-center text-xs text-muted-foreground space-x-4">
                        <span>{post.date}</span>
                        <span>•</span>
                        <span>{post.readTime}</span>
                        <span>•</span>
                        <span>{post.author}</span>
                      </div>
                      
                      <h2 className="text-xl lg:text-2xl font-light text-architectural group-hover:text-muted-foreground transition-colors duration-500">
                        {post.title}
                      </h2>
                      
                      <p className="text-muted-foreground leading-relaxed line-clamp-3">
                        {post.excerpt}
                      </p>
                      
                      <div className="pt-4">
                        <span className="text-minimal text-foreground hover:text-muted-foreground transition-colors duration-300 relative group-hover:underline">
                          READ MORE
                        </span>
                      </div>
                    </div>
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Newsletter Section */}
      <section className="py-32 bg-muted">
        <div className="container mx-auto px-6">
          <div className="max-w-4xl mx-auto text-center">
            <h2 className="text-4xl md:text-6xl font-light text-architectural mb-8">
              Stay Informed
            </h2>
            <p className="text-xl text-muted-foreground mb-12">
              Subscribe to our newsletter for the latest insights on architecture and design
            </p>
            <div className="flex flex-col sm:flex-row gap-4 max-w-lg mx-auto">
              <input 
                type="email" 
                placeholder="Enter your email"
                className="flex-1 px-6 py-4 bg-background border border-border text-foreground placeholder:text-muted-foreground"
              />
              <button className="px-8 py-4 bg-foreground text-background hover:bg-muted-foreground transition-colors duration-300">
                SUBSCRIBE
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Blog;