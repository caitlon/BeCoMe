import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/button";

// Three triangle forms to cycle through
const triangleForms = [
  { points: "60,160 180,60 300,160", peak: { cx: 180, cy: 60 }, centroid: 180 },
  { points: "80,160 200,40 320,160", peak: { cx: 200, cy: 40 }, centroid: 200 },
  { points: "100,160 220,50 340,160", peak: { cx: 220, cy: 50 }, centroid: 220 },
];

const smoothTransition = {
  duration: 0.8,
  ease: [0.25, 0.1, 0.25, 1] as const,
};

function motionAllowed() {
  if (typeof globalThis.matchMedia !== "function") return false;
  return !globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function FuzzyTriangleSVG() {
  const { t } = useTranslation();
  const { t: tLanding } = useTranslation("landing");
  const [currentForm, setCurrentForm] = useState(0);
  const [playing, setPlaying] = useState(motionAllowed);

  useEffect(() => {
    if (!playing) return;

    const interval = setInterval(() => {
      setCurrentForm(prev => (prev + 1) % triangleForms.length);
    }, 2000);
    return () => clearInterval(interval);
  }, [playing]);

  const current = triangleForms[currentForm];

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="absolute right-0 top-0 h-8 w-8 text-muted-foreground"
        aria-label={tLanding(playing ? "hero.pauseAnimation" : "hero.playAnimation")}
        onClick={() => setPlaying(prev => !prev)}
      >
        {playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
      </Button>
      <svg
        viewBox="0 0 400 200"
        className="w-full"
        role="img"
        aria-labelledby="fuzzy-triangle-title fuzzy-triangle-desc"
      >
        <title id="fuzzy-triangle-title">{t("fuzzy.triangleVisualization")}</title>
        <desc id="fuzzy-triangle-desc">{t("a11y.triangleDesc")}</desc>
        {/* Grid lines */}
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <rect
              width="40"
              height="40"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.1"
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <rect width="400" height="200" fill="url(#grid)" />
      
        {/* X-axis */}
        <line 
          x1="40" y1="160" x2="360" y2="160" 
          stroke="currentColor" 
          strokeOpacity="0.3" 
          strokeWidth="1"
        />
      
        {/* Y-axis */}
        <line 
          x1="40" y1="160" x2="40" y2="20" 
          stroke="currentColor" 
          strokeOpacity="0.3" 
          strokeWidth="1"
        />
      
        {/* Labels */}
        <text x="40" y="180" className="fill-muted-foreground text-xs">{t("fuzzy.lower")}</text>
        <text x="180" y="180" className="fill-muted-foreground text-xs">{t("fuzzy.peak")}</text>
        <text x="320" y="180" className="fill-muted-foreground text-xs">{t("fuzzy.upper")}</text>
        <text x="20" y="30" className="fill-muted-foreground text-xs">{t("fuzzy.membershipFunction")}</text>
      
        {/* Dashed triangle outlines (all three forms, static) */}
        {triangleForms.map((form, index) => (
          <polygon
            key={form.points}
            points={form.points}
            fill="none"
            stroke="currentColor"
            strokeOpacity={currentForm === index ? 0 : 0.15}
            strokeWidth="1"
            strokeDasharray="4,4"
            className="transition-all duration-300"
          />
        ))}
      
        {/* Main animated triangle */}
        <motion.polygon
          points={current.points}
          fill="currentColor"
          fillOpacity="0.08"
          stroke="currentColor"
          strokeWidth="2"
          initial={false}
          animate={{ 
            points: current.points,
          }}
          transition={smoothTransition}
        />
      
        {/* Peak marker */}
        <motion.circle
          r="4"
          fill="currentColor"
          initial={false}
          animate={{ 
            cx: current.peak.cx,
            cy: current.peak.cy,
          }}
          transition={smoothTransition}
        />
      
        {/* Peak projection line */}
        <motion.line
          y1="160"
          stroke="currentColor"
          strokeWidth="1"
          strokeDasharray="2,2"
          strokeOpacity="0.4"
          initial={false}
          animate={{
            x1: current.centroid,
            x2: current.centroid,
            y2: current.peak.cy,
          }}
          transition={smoothTransition}
        />
      </svg>
    </div>
  );
}
