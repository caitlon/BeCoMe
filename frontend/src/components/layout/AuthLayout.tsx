import { motion } from "framer-motion";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Navbar } from "@/components/layout/Navbar";

interface AuthLayoutProps {
  title: string;
  children: React.ReactNode;
}

export function AuthLayout({ title, children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main id="main-content" className="flex-1 flex items-center justify-center py-12 px-6">
        <motion.div
          className="w-full max-w-md"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Card className="border-border/50">
            <CardHeader className="text-center pb-2">
              <CardTitle as="h1" className="font-display text-2xl font-normal">
                {title}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">{children}</CardContent>
          </Card>
        </motion.div>
      </main>
    </div>
  );
}
