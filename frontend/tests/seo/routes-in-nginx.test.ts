import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { publicRoutes } from '@/seo/publicRoutes';

const frontendDir = path.resolve(import.meta.dirname, '../..');
const appSource = readFileSync(path.join(frontendDir, 'src/App.tsx'), 'utf8');
const nginxConf = readFileSync(path.join(frontendDir, 'nginx.conf'), 'utf8');

// nginx answers 200 for a path only when the build prerendered it or this allowlist names it, and
// 404 otherwise. A route added to src/App.tsx and to neither would ship as a 404 in production.
const ALLOWLIST_LOCATION = /^\s*location\s+~\s+(\^\/\(([^)]+)\)\/\?\\z)\s*\{/m;
// Every regex location, the asset one included, with its pattern.
const REGEX_LOCATIONS = /^\s*location\s+~\*?\s+(\S+)\s*\{/gm;

// nginx ends its patterns in \z, the absolute end of the subject, because PCRE's `$` also matches
// before a trailing newline (and nginx matches the decoded URI, so /login%0A would match). JS has no
// \z, and a JS `$` without the m flag matches only at the very end, which is what \z means, so the
// pattern is translated for the test.
function toJsPattern(nginxPattern: string): RegExp {
  return new RegExp(nginxPattern.replace(/\\z$/, '$'));
}

function appRoutes(source: string): string[] {
  return [...source.matchAll(/<Route\s+path="([^"]+)"/g)].map((match) => match[1]).filter((route) => route !== '*');
}

// A route as nginx's pattern writes it: a parameter matches one path segment without whitespace.
function asRegexSource(route: string): string {
  return route.replace(/:\w+/g, '[^/\\s]+');
}

function routeProblems(source: string, conf: string, publicPaths: readonly string[]): string[] {
  const location = ALLOWLIST_LOCATION.exec(conf);
  if (!location) return ['nginx.conf has no allowlist location'];
  const pattern = toJsPattern(location[1]);
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
      const pattern = toJsPattern(ALLOWLIST_LOCATION.exec(nginxConf)?.[1] ?? '$^');
      expect(pattern.test(candidate)).toBe(false);
    },
  );

  it.each(['/login', '/login/', '/projects', '/projects/', '/projects/123', '/projects/123/', '/profile/'])(
    'allowlists %s',
    (candidate) => {
      const pattern = toJsPattern(ALLOWLIST_LOCATION.exec(nginxConf)?.[1] ?? '$^');
      expect(pattern.test(candidate)).toBe(true);
    },
  );

  it('ends every regex location in \\z, never $, so a trailing newline does not match', () => {
    const patterns = [...nginxConf.matchAll(REGEX_LOCATIONS)].map((match) => match[1]);

    expect(patterns).toHaveLength(2);
    for (const pattern of patterns) {
      expect(pattern.endsWith('\\z'), `${pattern} must end in \\z`).toBe(true);
    }
  });

  it('does not match an allowlisted route followed by a newline (/login%0A decodes to /login\\n)', () => {
    const location = ALLOWLIST_LOCATION.exec(nginxConf);
    if (!location) throw new Error('nginx.conf has no allowlist location');
    const pattern = toJsPattern(location[1]);
    const samples = location[2].split('|').map((alternative) => alternative.replace('[^/\\s]+', 'sample-1'));

    expect(samples).toContain('login');
    expect(samples).toContain('projects/sample-1');
    for (const alternative of samples) {
      expect(pattern.test(`/${alternative}`), `/${alternative} matches`).toBe(true);
      expect(pattern.test(`/${alternative}\n`), `/${alternative}\\n must not match`).toBe(false);
      expect(pattern.test(`/${alternative}/\n`), `/${alternative}/\\n must not match`).toBe(false);
    }
  });

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
