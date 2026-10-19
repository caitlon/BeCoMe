import { describe, it, expect } from 'vitest';
import i18n from '@/i18n';

const chart = { min: 1, max: 9, mean: 4, median: 5, compromise: 5 };

type Case = { ns: string; key: string; count: number; expected: string; extra?: object };

const cs: Case[] = [
  { ns: 'projects', key: 'invitations.pending', count: 1, expected: 'Máte 1 čekající pozvánku' },
  { ns: 'projects', key: 'invitations.pending', count: 2, expected: 'Máte 2 čekající pozvánky' },
  { ns: 'projects', key: 'invitations.pending', count: 5, expected: 'Máte 5 čekajících pozvánek' },
  { ns: 'projects', key: 'detail.teamMembers', count: 1, expected: 'Tým (1 člen)' },
  { ns: 'projects', key: 'detail.teamMembers', count: 2, expected: 'Tým (2 členové)' },
  { ns: 'projects', key: 'detail.teamMembers', count: 5, expected: 'Tým (5 členů)' },
  {
    ns: 'common', key: 'centroidChart.srSummary', count: 1, extra: chart,
    expected: '1 expert, centroidy od 1 do 9. Průměr: 4, Medián: 5, Nejlepší kompromis: 5.',
  },
  {
    ns: 'common', key: 'centroidChart.srSummary', count: 2, extra: chart,
    expected: '2 experti, centroidy od 1 do 9. Průměr: 4, Medián: 5, Nejlepší kompromis: 5.',
  },
  {
    ns: 'common', key: 'centroidChart.srSummary', count: 5, extra: chart,
    expected: '5 expertů, centroidy od 1 do 9. Průměr: 4, Medián: 5, Nejlepší kompromis: 5.',
  },
  {
    ns: 'common', key: 'landscapeChart.srSummary', count: 1, extra: chart,
    expected: '1 expertní názor rozprostřený od 1 do 9; nejlepší kompromis leží na hodnotě 5.',
  },
  {
    ns: 'common', key: 'landscapeChart.srSummary', count: 2, extra: chart,
    expected: '2 expertní názory rozprostřené od 1 do 9; nejlepší kompromis leží na hodnotě 5.',
  },
  {
    ns: 'common', key: 'landscapeChart.srSummary', count: 5, extra: chart,
    expected: '5 expertních názorů rozprostřených od 1 do 9; nejlepší kompromis leží na hodnotě 5.',
  },
];

const en: Case[] = [
  { ns: 'projects', key: 'invitations.pending', count: 1, expected: 'You have 1 pending invitation' },
  { ns: 'projects', key: 'invitations.pending', count: 2, expected: 'You have 2 pending invitations' },
  { ns: 'projects', key: 'detail.teamMembers', count: 1, expected: 'Team (1 member)' },
  { ns: 'projects', key: 'detail.teamMembers', count: 2, expected: 'Team (2 members)' },
  {
    ns: 'common', key: 'centroidChart.srSummary', count: 1, extra: chart,
    expected: '1 expert, centroids from 1 to 9. Mean: 4, Median: 5, Best Compromise: 5.',
  },
  {
    ns: 'common', key: 'centroidChart.srSummary', count: 2, extra: chart,
    expected: '2 experts, centroids from 1 to 9. Mean: 4, Median: 5, Best Compromise: 5.',
  },
  {
    ns: 'common', key: 'landscapeChart.srSummary', count: 1, extra: chart,
    expected: '1 expert opinion spread from 1 to 9; the best compromise sits at 5.',
  },
  {
    ns: 'common', key: 'landscapeChart.srSummary', count: 2, extra: chart,
    expected: '2 expert opinions spread from 1 to 9; the best compromise sits at 5.',
  },
];

describe('plural forms of counted UI strings', () => {
  it.each(cs)('cs $ns:$key with count $count', ({ ns, key, count, expected, extra }) => {
    expect(i18n.getFixedT('cs', ns)(key, { count, ...extra })).toBe(expected);
  });

  it.each(en)('en $ns:$key with count $count', ({ ns, key, count, expected, extra }) => {
    expect(i18n.getFixedT('en', ns)(key, { count, ...extra })).toBe(expected);
  });
});
