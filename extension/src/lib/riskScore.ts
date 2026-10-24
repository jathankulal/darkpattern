import type { Finding, FindingCategory, FindingSeverity } from '../types/api';

export interface RiskAssessment {
  score: number | null;
  label: string;
  verdict: string;
  contributors: Finding[];
}

const SEVERITY_POINTS: Record<FindingSeverity, number> = {
  info: 0,
  low: 20,
  medium: 40,
  high: 60,
};

const EVIDENCE_MULTIPLIERS = {
  explicit: 1,
  inferred: 0.6,
  unknown: 0,
} as const;

const SCORABLE_CATEGORIES = new Set<FindingCategory>([
  'urgency_pressure',
  'future_charge_disclosure',
]);

function categoryDescription(category: FindingCategory): string {
  switch (category) {
    case 'urgency_pressure':
      return 'time-pressure language';
    case 'future_charge_disclosure':
      return 'a trial with no clear renewal price';
    default:
      return 'a supported warning sign';
  }
}

function unscoredConcernDescription(category: FindingCategory): string | null {
  switch (category) {
    case 'additional_fee':
      return 'an unexplained checkout difference';
    case 'missing_commitment_info':
      return 'cancellation information not found in the text checked';
    case 'cancellation_refund_clarity':
      return 'cancellation or refund wording that needs review';
    case 'future_charge_disclosure':
      return 'unclear trial-renewal terms';
    default:
      return null;
  }
}

export function getRiskLabel(score: number): string {
  if (score < 20) return 'Low Detected Risk';
  if (score < 40) return 'Some Warning Signs';
  if (score < 60) return 'Moderate Risk';
  if (score < 80) return 'High Risk';
  return 'Very High Risk';
}

export function assessDarkPatternRisk(findings: Finding[]): RiskAssessment {
  const strongestByCategory = new Map<FindingCategory, { finding: Finding; points: number }>();

  for (const finding of findings) {
    if (
      !SCORABLE_CATEGORIES.has(finding.category) ||
      finding.evidence_level === 'unknown' ||
      !finding.evidence_text.trim() ||
      finding.confidence <= 0
    ) {
      continue;
    }

    const points = Math.round(
      SEVERITY_POINTS[finding.severity] *
        EVIDENCE_MULTIPLIERS[finding.evidence_level] *
        finding.confidence,
    );
    if (points <= 0) continue;

    const previous = strongestByCategory.get(finding.category);
    if (!previous || points > previous.points) {
      strongestByCategory.set(finding.category, { finding, points });
    }
  }

  const contributions = [...strongestByCategory.values()];
  if (contributions.length === 0) {
    const unscoredConcerns = [...new Set(
      findings
        .map((finding) => unscoredConcernDescription(finding.category))
        .filter((description): description is string => description !== null),
    )];
    return {
      score: null,
      label: 'Insufficient evidence to score',
      verdict: unscoredConcerns.length > 0
        ? `There is not enough supported evidence to assign a dark-pattern score. The scan also noted ${unscoredConcerns.join(' and ')}; review these, but they are not included in the score.`
        : 'There is not enough supported dark-pattern evidence to assign a score. This scan does not prove that the page is safe.',
      contributors: [],
    };
  }

  const score = Math.min(
    100,
    contributions.reduce((total, contribution) => total + contribution.points, 0),
  );
  const label = getRiskLabel(score);
  const indicators = contributions
    .map(({ finding }) => categoryDescription(finding.category))
    .join(' and ');

  return {
    score,
    label,
    verdict: `${label}: the scan found ${indicators}. This is an evidence-based indicator, not a probability that the site is deceptive.`,
    contributors: contributions.map(({ finding }) => finding),
  };
}

export function getPrimaryFindings(findings: Finding[]): Finding[] {
  const candidates = findings
    .filter(
      (finding) =>
        finding.severity !== 'info' &&
        finding.category !== 'recurring_payment' &&
        finding.category !== 'free_trial_conversion',
    )
    .sort((a, b) => {
      const severityOrder: Record<FindingSeverity, number> = {
        info: 0,
        low: 1,
        medium: 2,
        high: 3,
      };
      const evidenceOrder = { unknown: 0, inferred: 1, explicit: 2 };
      return (
        severityOrder[b.severity] - severityOrder[a.severity] ||
        evidenceOrder[b.evidence_level] - evidenceOrder[a.evidence_level] ||
        b.confidence - a.confidence
      );
    });

  const seenCategories = new Set<FindingCategory>();
  return candidates.filter((finding) => {
    if (seenCategories.has(finding.category)) return false;
    seenCategories.add(finding.category);
    return true;
  }).slice(0, 3);
}
