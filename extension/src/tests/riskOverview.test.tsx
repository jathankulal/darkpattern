import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RiskOverview } from '../components/RiskOverview';
import {
  assessDarkPatternRisk,
  getPrimaryFindings,
  getRiskLabel,
} from '../lib/riskScore';
import type { AnalyzeResponse, Finding } from '../types/api';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'finding-urgency',
    category: 'urgency_pressure',
    severity: 'low',
    evidence_level: 'explicit',
    evidence_text: 'Offer ends in 10 minutes.',
    explanation: 'Urgency language was found.',
    confidence: 0.85,
    missing_information: [],
    recommendation: 'Take time to decide.',
    ...overrides,
  };
}

function makeResponse(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    status: 'ok',
    summary: 'Analysis summary.',
    findings: [],
    commitment_map: { unknowns: [] },
    plans: [],
    price_integrity: { observations: [], reason: 'known' },
    checklist: [],
    limitations: [],
    ...overrides,
  };
}

describe('dark-pattern risk overview', () => {
  it('does not score a clearly disclosed recurring subscription by itself', () => {
    const findings = [
      makeFinding({
        id: 'recurring',
        category: 'recurring_payment',
        severity: 'info',
        evidence_text: 'Renews at USD 29 monthly.',
      }),
      makeFinding({
        id: 'trial',
        category: 'free_trial_conversion',
        severity: 'info',
        evidence_text: 'A 14-day trial then renews at USD 29 monthly.',
      }),
    ];

    expect(assessDarkPatternRisk(findings).score).toBeNull();
    render(<RiskOverview data={makeResponse({ findings })} />);

    expect(screen.getByText('Insufficient evidence to score')).toBeDefined();
    expect(screen.queryByText('29')).toBeNull();
    expect(screen.getByText(/does not prove that the page is safe/i)).toBeDefined();
  });

  it('scores an explicit supported urgency indicator and keeps verdict and label aligned', () => {
    const finding = makeFinding();
    const assessment = assessDarkPatternRisk([finding]);

    expect(assessment.score).toBe(17);
    expect(assessment.label).toBe('Low Detected Risk');
    expect(assessment.verdict).toContain('Low Detected Risk');
    expect(assessment.verdict).toContain('time-pressure language');
    expect(assessment.contributors).toEqual([finding]);

    render(<RiskOverview data={makeResponse({ findings: [finding] })} />);
    expect(screen.getByRole('meter', { name: 'Dark-pattern risk score 17 out of 100' })).toBeDefined();
    expect(screen.getByText('Low Detected Risk')).toBeDefined();
    expect(screen.getByText('Final verdict')).toBeDefined();
    expect(screen.getByText('Offer ends in 10 minutes.', { selector: 'blockquote' })).toBeDefined();
    expect(screen.getByText(/Take time to decide/)).toBeDefined();
  });

  it('scores a missing trial-renewal price only when its quote is present', () => {
    const finding = makeFinding({
      id: 'trial-without-price',
      category: 'future_charge_disclosure',
      severity: 'high',
      evidence_level: 'explicit',
      evidence_text: 'Start your 14-day free trial today.',
      confidence: 0.9,
    });
    const assessment = assessDarkPatternRisk([finding]);

    expect(assessment.score).toBe(54);
    expect(assessment.label).toBe('Moderate Risk');
    expect(assessment.verdict).toContain('a trial with no clear renewal price');
    expect(assessment.contributors).toEqual([finding]);
  });

  it('shows checkout differences as financial concerns without scoring them as deception', () => {
    const finding = makeFinding({
      id: 'checkout-difference',
      category: 'additional_fee',
      severity: 'high',
      evidence_text: 'Order Total: $65.00',
      explanation: 'There is an unexplained difference.',
    });
    const data = makeResponse({
      findings: [finding],
      price_integrity: {
        observations: [],
        reason: 'unclear',
        unexplained_difference: { amount: '8.00', currency: 'USD', kind: 'fee' },
      },
    });

    expect(assessDarkPatternRisk([finding]).score).toBeNull();
    render(<RiskOverview data={data} />);

    expect(screen.getByText('Insufficient evidence to score')).toBeDefined();
    expect(screen.getByText('Unexplained checkout difference')).toBeDefined();
    expect(screen.getByText(/USD 8.00 is not accounted for.*not proof of deception/i)).toBeDefined();
    expect(
      screen.getAllByText(/financial concern, not proof of deception/i).length,
    ).toBeGreaterThan(0);
  });

  it('counts only the strongest finding in each category', () => {
    const strongest = makeFinding({
      id: 'stronger-urgency',
      severity: 'low',
      confidence: 0.8,
    });
    const overlapping = makeFinding({
      id: 'overlapping-urgency',
      severity: 'medium',
      evidence_level: 'inferred',
      confidence: 0.5,
      evidence_text: 'Only a few left.',
    });
    const assessment = assessDarkPatternRisk([strongest, overlapping]);

    expect(assessment.score).toBe(16);
    expect(assessment.contributors).toEqual([strongest]);
  });

  it('returns insufficient evidence for missing quotes and unknown evidence levels', () => {
    const unsupported = makeFinding({
      evidence_level: 'unknown',
      evidence_text: '',
    });

    expect(assessDarkPatternRisk([unsupported]).score).toBeNull();
    render(<RiskOverview data={makeResponse({ findings: [unsupported] })} />);
    expect(screen.getByText('Insufficient evidence to score')).toBeDefined();
    expect(screen.queryByText('0')).toBeNull();

    const missingCancellation = makeFinding({
      id: 'missing-cancellation',
      category: 'missing_commitment_info',
      severity: 'low',
      evidence_level: 'unknown',
      evidence_text: '',
    });
    const unscoredAssessment = assessDarkPatternRisk([missingCancellation]);
    expect(unscoredAssessment.score).toBeNull();
    expect(unscoredAssessment.verdict).toContain(
      'cancellation information not found in the text checked',
    );
  });

  it('uses the defined score bands and selects distinct, serious main issues first', () => {
    expect([0, 19, 20, 39, 40, 59, 60, 79, 80].map(getRiskLabel)).toEqual([
      'Low Detected Risk',
      'Low Detected Risk',
      'Some Warning Signs',
      'Some Warning Signs',
      'Moderate Risk',
      'Moderate Risk',
      'High Risk',
      'High Risk',
      'Very High Risk',
    ]);

    const primary = getPrimaryFindings([
      makeFinding({ id: 'low-urgency', category: 'urgency_pressure', severity: 'low' }),
      makeFinding({ id: 'high-urgency', category: 'urgency_pressure', severity: 'high' }),
      makeFinding({ id: 'fee', category: 'additional_fee', severity: 'high' }),
      makeFinding({
        id: 'missing-cancellation',
        category: 'missing_commitment_info',
        severity: 'medium',
        evidence_level: 'unknown',
        evidence_text: '',
      }),
      makeFinding({
        id: 'ordinary-renewal',
        category: 'recurring_payment',
        severity: 'info',
      }),
    ]);

    expect(primary.map((finding) => finding.id)).toEqual([
      'high-urgency',
      'fee',
      'missing-cancellation',
    ]);
  });
});
