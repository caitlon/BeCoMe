import { useParams, Link } from "react-router-dom";
import Navigation from "@/components/Navigation";
import { blogPosts } from "@/data/blogPosts";

const BlogPost = () => {
  const { id } = useParams<{ id: string }>();
  const post = blogPosts.find(p => p.id === id);

  if (!post) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <div className="pt-32 pb-32">
          <div className="container mx-auto px-6">
            <div className="max-w-4xl mx-auto text-center">
              <h1 className="text-4xl md:text-6xl font-light text-architectural mb-8">
                Post Not Found
              </h1>
              <Link 
                to="/blog" 
                className="text-minimal text-foreground hover:text-muted-foreground transition-colors duration-300"
              >
                ← BACK TO BLOG
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      {/* Article Header */}
      <article className="pt-32 pb-32">
        <div className="container mx-auto px-6">
          <div className="max-w-4xl mx-auto">
            {/* Back Link */}
            <Link 
              to="/blog" 
              className="inline-block text-minimal text-muted-foreground hover:text-foreground transition-colors duration-300 mb-12"
            >
              ← BACK TO BLOG
            </Link>
            
            {/* Article Meta */}
            <div className="mb-8">
              <div className="flex items-center text-minimal text-muted-foreground space-x-4 mb-6">
                <span className="bg-muted px-3 py-1 text-foreground">{post.category}</span>
                <span>{post.date}</span>
                <span>•</span>
                <span>{post.readTime}</span>
                <span>•</span>
                <span>{post.author}</span>
              </div>
              
              <h1 className="text-4xl md:text-6xl font-light text-architectural mb-6">
                {post.title}
              </h1>
              
              <p className="text-xl text-muted-foreground leading-relaxed">
                {post.excerpt}
              </p>
            </div>
            
            {/* Featured Image */}
            <div className="w-full h-96 mb-12 overflow-hidden">
              <img 
                src={post.image} 
                alt={post.title}
                className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
              />
            </div>
            
            {/* Article Content */}
            <div className="prose prose-lg max-w-none">
              <div 
                className="text-muted-foreground leading-relaxed space-y-6"
                dangerouslySetInnerHTML={{ 
                  __html: post.content
                    .split('\n')
                    .map(line => {
                      if (line.startsWith('# ')) {
                        return `<h1 class="text-3xl md:text-4xl font-light text-architectural mb-8 mt-12">${line.substring(2)}</h1>`;
                      } else if (line.startsWith('## ')) {
                        return `<h2 class="text-2xl md:text-3xl font-light text-architectural mb-6 mt-10">${line.substring(3)}</h2>`;
                      } else if (line.startsWith('### ')) {
                        return `<h3 class="text-xl md:text-2xl font-medium text-foreground mb-4 mt-8">${line.substring(4)}</h3>`;
                      } else if (line.startsWith('- **') && line.endsWith('**')) {
                        const content = line.substring(4, line.length - 2);
                        return `<li class="ml-6 mb-2"><strong class="text-foreground">${content}</strong></li>`;
                      } else if (line.startsWith('- ')) {
                        return `<li class="ml-6 mb-2">${line.substring(2)}</li>`;
                      } else if (line.trim() === '') {
                        return '<br>';
                      } else if (line.startsWith('**') && line.endsWith('**')) {
                        return `<p class="mb-4"><strong class="text-foreground">${line.substring(2, line.length - 2)}</strong></p>`;
                      } else {
                        return `<p class="mb-4">${line}</p>`;
                      }
                    })
                    .join('')
                }}
              />
            </div>
            
            {/* Author Info */}
            <div className="mt-16 pt-8 border-t border-border">
              <div className="flex items-center space-x-4">
                <div className="w-16 h-16 bg-muted rounded-full"></div>
                <div>
                  <h3 className="text-lg font-medium text-foreground">{post.author}</h3>
                  <p className="text-muted-foreground">Architect & Writer</p>
                </div>
              </div>
            </div>
            
            {/* Related Posts */}
            <div className="mt-20">
              <h3 className="text-2xl font-light text-architectural mb-8">Related Articles</h3>
              <div className="grid md:grid-cols-2 gap-8">
                {blogPosts
                  .filter(p => p.id !== post.id && p.category === post.category)
                  .slice(0, 2)
                  .map(relatedPost => (
                    <Link key={relatedPost.id} to={`/blog/${relatedPost.id}`} className="group">
                      <div className="w-full h-48 mb-4 overflow-hidden">
                        <img 
                          src={relatedPost.image} 
                          alt={relatedPost.title}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                        />
                      </div>
                      <h4 className="text-lg font-light text-architectural group-hover:text-muted-foreground transition-colors duration-300 mb-2">
                        {relatedPost.title}
                      </h4>
                      <p className="text-minimal text-muted-foreground">{relatedPost.date} • {relatedPost.readTime}</p>
                    </Link>
                  ))
                }
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>
  );
};

export default BlogPost;