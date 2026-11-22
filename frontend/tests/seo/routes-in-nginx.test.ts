import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { publicRoutes } from '@/seo/publicRoutes';

const frontendDir = path.resolve(import.meta.dirname, '../..');
const appSource = readFileSync(path.join(frontendDir, 'src/App.tsx'), 'utf8');
const nginxConf = readFileSync(path.join(frontendDir, 'nginx.conf'), 'utf8');

// nginx answers 200 for a path only when the build prerendered it or this allowlist names it, and
// 404 otherwise. A route added to src/App.tsx and to neither would ship as a 404 in production.
const ALLOWLIST_LOCATION = /^\s*location\s+~\s+(\^\/\(([^)]+)\)\/\?\$)\s*\{/m;

function appRoutes(source: string): string[] {
  return [...source.matchAll(/<Route\s+path="([^"]+)"/g)].map((match) => match[1]).filter((route) => route !== '*');
}

// A route as nginx's pattern writes it: a parameter matches one path segment.
function asRegexSource(route: string): string {
  return route.replace(/:\w+/g, '[^/]+');
}

function routeProblems(source: string, conf: string, publicPaths: readonly string[]): string[] {
  const location = ALLOWLIST_LOCATION.exec(conf);
  if (!location) return ['nginx.conf has no allowlist location'];
  const pattern = new RegExp(location[1]);
  const alternatives = location[2].split('|');
  const routes = appRoutes(source);
  const problems: string[] = [];

  for (const route of routes) {
    const routePattern = new RegExp(`^${asRegexSource(route)}$`);
    const prerendered = publicPaths.some((candidate) => routePattern.test(candidate));
    const sample = route.replace(/:\w+/g, 'sample-1');
    const allowed = pattern.test(sample) && pattern.test(`${sample}/`);
    if (prerendered && allowed) problems.push(`${route} is both prerendered and in the nginx allowlist`);
    if (!prerendered && !allowed) problems.push(`${route} is neither prerendered nor in the nginx allowlist`);
  }
  const known = routes.map((route) => asRegexSource(route.slice(1)));
  for (const alternative of alternatives) {
    if (!known.includes(alternative)) problems.push(`the nginx allowlist names ${alternative}, which is no route of App.tsx`);
  }
  for (const candidate of publicPaths) {
    if (!routes.some((route) => new RegExp(`^${asRegexSource(route)}$`).test(candidate))) {
      problems.push(`${candidate} is a public route but no route of App.tsx`);
    }
  }
  return problems;
}

describe('the routes of App.tsx, the prerendered pages and the nginx allowlist', () => {
  it('read the routes out of the source', () => {
    expect(appRoutes(appSource)).toContain('/projects/:id');
    expect(appRoutes(appSource)).not.toContain('*');
  });

  it('agree: each route is prerendered or allowlisted, never both, and the allowlist holds nothing else', () => {
    expect(routeProblems(appSource, nginxConf, publicRoutes)).toEqual([]);
  });

  it.each(['/about', '/case-study/', '/loginx', '/projects/a/b', '/projects//', '/assets/app.js', '/spa.html'])(
    'does not allowlist %s',
    (candidate) => {
      const pattern = new RegExp(ALLOWLIST_LOCATION.exec(nginxConf)?.[1] ?? '$^');
      expect(pattern.test(candidate)).toBe(false);
    },
  );

  it.each(['/login', '/login/', '/projects', '/projects/', '/projects/123', '/projects/123/', '/profile/'])(
    'allowlists %s',
    (candidate) => {
      const pattern = new RegExp(ALLOWLIST_LOCATION.exec(nginxConf)?.[1] ?? '$^');
      expect(pattern.test(candidate)).toBe(true);
    },
  );

  it('fails for a route added to App.tsx alone', () => {
    const added = appSource.replace('<Route path="*"', '<Route path="/billing" element={<div />} />\n<Route path="*"');

    expect(routeProblems(added, nginxConf, publicRoutes)).toEqual([
      '/billing is neither prerendered nor in the nginx allowlist',
    ]);
  });

  it('fails for a public route that App.tsx does not have', () => {
    expect(routeProblems(appSource, nginxConf, [...publicRoutes, '/pricing'])).toEqual([
      '/pricing is a public route but no route of App.tsx',
    ]);
  });

  it('fails for an allowlist alternative that App.tsx does not have', () => {
    const extended = nginxConf.replace('|onboarding)', '|onboarding|billing)');

    expect(routeProblems(appSource, extended, publicRoutes)).toEqual([
      'the nginx allowlist names billing, which is no route of App.tsx',
    ]);
  });

  it('fails for a route that is allowlisted and prerendered at once', () => {
    expect(routeProblems(appSource, nginxConf, [...publicRoutes, '/profile'])).toEqual([
      '/profile is both prerendered and in the nginx allowlist',
    ]);
  });

  it('fails for a route dropped from the allowlist', () => {
    const shortened = nginxConf.replace('|profile|', '|');

    expect(routeProblems(appSource, shortened, publicRoutes)).toEqual([
      '/profile is neither prerendered nor in the nginx allowlist',
    ]);
  });
});
