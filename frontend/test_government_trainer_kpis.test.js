import test from 'node:test';
import assert from 'node:assert/strict';

function resolveTrainerKpiState({ loading, hasError, statewideTrainers, valueExtractor }) {
  if (loading && !statewideTrainers) {
    return 'LOADING';
  }
  if (hasError) {
    return 'UNAVAILABLE';
  }
  return valueExtractor(statewideTrainers);
}

test('initial load without statewideTrainers resolves to LOADING state', () => {
  const result = resolveTrainerKpiState({
    loading: true,
    hasError: false,
    statewideTrainers: null,
    valueExtractor: (data) => `${data?.summary?.statewide_compliance_ratio_pct ?? 0}%`,
  });
  assert.equal(result, 'LOADING');
});

test('error state resolves to UNAVAILABLE', () => {
  const result = resolveTrainerKpiState({
    loading: false,
    hasError: true,
    statewideTrainers: null,
    valueExtractor: (data) => `${data?.summary?.statewide_compliance_ratio_pct ?? 0}%`,
  });
  assert.equal(result, 'UNAVAILABLE');
});

test('refresh with existing statewideTrainers retains loaded value rather than loading state', () => {
  const previousData = {
    summary: {
      statewide_compliance_ratio_pct: 85.5,
      active_trainers: 42,
      certified_trainers_count: 18,
    },
  };
  const result = resolveTrainerKpiState({
    loading: true,
    hasError: false,
    statewideTrainers: previousData,
    valueExtractor: (data) => `${data?.summary?.statewide_compliance_ratio_pct ?? 0}%`,
  });
  assert.equal(result, '85.5%');
});

test('zero counts are preserved as valid numeric values', () => {
  const zeroData = {
    summary: {
      statewide_compliance_ratio_pct: 0,
      active_trainers: 0,
      certified_trainers_count: 0,
    },
  };
  const result = resolveTrainerKpiState({
    loading: false,
    hasError: false,
    statewideTrainers: zeroData,
    valueExtractor: (data) => data?.summary?.active_trainers ?? 0,
  });
  assert.equal(result, 0);
});
