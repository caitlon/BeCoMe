import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { caseStudies } from '@/data/caseStudies';

const ORIGIN = 'https://www.becomify.app';
const root = path.resolve(__dirname, '../..');
const read = (file: string) => readFileSync(path.join(root, file), 'utf8');

const sitemap = read('public/sitemap.xml');
const robots = read('public/robots.txt');
const appSource = read('src/App.tsx');

const locs = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1]);
const paths = locs.map(loc => loc.slice(ORIGIN.length));
const staticRoutes = [...appSource.matchAll(/path="([^"]+)"/g)].map(m => m[1]);
const disallowed = [...robots.matchAll(/^Disallow:\s*(\S+)/gm)].map(m => m[1]);

describe('sitemap.xml', () => {
  it('lists absolute URLs on the production origin', () => {
    // GIVEN the sitemap entries
    // THEN each one starts with the production origin
    expect(locs.length).toBeGreaterThan(0);
    locs.forEach(loc => expect(loc.startsWith(`${ORIGIN}/`)).toBe(true));
  });

  it('points case-study URLs at existing case studies', () => {
    // GIVEN the case-study entries
    const ids = paths.filter(p => p.startsWith('/case-study/')).map(p => p.split('/')[2]);

    // THEN every id exists in the case study data
    expect(ids.length).toBeGreaterThan(0);
    ids.forEach(id => expect(caseStudies.map(cs => cs.id)).toContain(id));
  });

  it('lists only routes that App.tsx declares', () => {
    // GIVEN the entries that are not case-study pages
    const others = paths.filter(p => !p.startsWith('/case-study/'));

    // THEN each one is a static route of the app
    others.forEach(p => expect(staticRoutes).toContain(p));
  });

  it('does not list a page that robots.txt disallows', () => {
    // GIVEN the Disallow rules
    // THEN no sitemap path falls under one of them
    paths.forEach(p => {
      expect(disallowed.some(rule => p === rule || p.startsWith(`${rule}/`))).toBe(false);
    });
  });
});

describe('robots.txt', () => {
  it('has one group and announces the sitemap', () => {
    // GIVEN the robots.txt content
    // THEN there is exactly one User-agent line and the Sitemap line
    expect(robots.match(/^User-agent:/gm)).toHaveLength(1);
    expect(robots).toContain(`Sitemap: ${ORIGIN}/sitemap.xml`);
  });
});
