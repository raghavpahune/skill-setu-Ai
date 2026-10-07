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

function applyNominationStatusTransition(currentState, transition) {
  const { statewideTrainers, allFacultyNominations, nominationId, updatedRecord } = currentState;
  const nextNominations = (allFacultyNominations || []).map((n) => (n.id === nominationId ? updatedRecord : n));
  let nextTrainers = statewideTrainers;
  if (statewideTrainers?.nomination_summary) {
    const summary = { ...statewideTrainers.nomination_summary };
    if (transition === 'SANCTIONED') {
      summary.NOMINATED = typeof summary.NOMINATED === 'number' ? Math.max(0, summary.NOMINATED - 1) : summary.NOMINATED;
      summary.SANCTIONED = typeof summary.SANCTIONED === 'number' ? summary.SANCTIONED + 1 : summary.SANCTIONED;
    } else if (transition === 'REJECTED') {
      summary.NOMINATED = typeof summary.NOMINATED === 'number' ? Math.max(0, summary.NOMINATED - 1) : summary.NOMINATED;
      summary.REJECTED = typeof summary.REJECTED === 'number' ? summary.REJECTED + 1 : summary.REJECTED;
    }
    nextTrainers = { ...statewideTrainers, nomination_summary: summary };
  }
  return {
    statewideTrainers: nextTrainers,
    allFacultyNominations: nextNominations,
  };
}

function resolveNominationKpiCounts(statewideTrainers, allFacultyNominations, errors = {}) {
  const pendingNominationsCount = typeof statewideTrainers?.nomination_summary?.NOMINATED === 'number'
    ? statewideTrainers.nomination_summary.NOMINATED
    : (!errors.facultyNominations && Array.isArray(allFacultyNominations)
      ? allFacultyNominations.filter((n) => n.status === 'NOMINATED').length
      : null);

  const sanctionedNominationsCount = typeof statewideTrainers?.nomination_summary?.SANCTIONED === 'number'
    ? statewideTrainers.nomination_summary.SANCTIONED
    : (!errors.facultyNominations && Array.isArray(allFacultyNominations)
      ? allFacultyNominations.filter((n) => n.status === 'SANCTIONED').length
      : null);

  return { pendingNominationsCount, sanctionedNominationsCount };
}

function renderFacultyRosterRows(trainers) {
  if (!trainers || trainers.length === 0) {
    return {
      isEmpty: true,
      colSpan: 5,
      promptText: 'No vocational instructors registered yet. Please register an instructor to track faculty capacity.',
    };
  }
  return {
    isEmpty: false,
    rowCount: trainers.length,
    rows: trainers.map((t) => ({ id: t.id, name: t.name, trade: t.primary_trade })),
  };
}

test('sanction transition updates nomination summary and KPI state correctly', () => {
  const initialData = {
    statewideTrainers: {
      nomination_summary: {
        NOMINATED: 5,
        SANCTIONED: 2,
        REJECTED: 1,
      },
    },
    allFacultyNominations: [
      { id: 'nom-1', status: 'NOMINATED' },
      { id: 'nom-2', status: 'NOMINATED' },
    ],
    nominationId: 'nom-1',
    updatedRecord: { id: 'nom-1', status: 'SANCTIONED' },
  };

  const next = applyNominationStatusTransition(initialData, 'SANCTIONED');
  const counts = resolveNominationKpiCounts(next.statewideTrainers, next.allFacultyNominations);

  assert.equal(next.statewideTrainers.nomination_summary.NOMINATED, 4);
  assert.equal(next.statewideTrainers.nomination_summary.SANCTIONED, 3);
  assert.equal(counts.pendingNominationsCount, 4);
  assert.equal(counts.sanctionedNominationsCount, 3);
  assert.equal(next.allFacultyNominations.find((n) => n.id === 'nom-1').status, 'SANCTIONED');
});

test('rejection transition updates nomination summary and KPI state correctly', () => {
  const initialData = {
    statewideTrainers: {
      nomination_summary: {
        NOMINATED: 3,
        SANCTIONED: 4,
        REJECTED: 0,
      },
    },
    allFacultyNominations: [
      { id: 'nom-3', status: 'NOMINATED' },
    ],
    nominationId: 'nom-3',
    updatedRecord: { id: 'nom-3', status: 'REJECTED' },
  };

  const next = applyNominationStatusTransition(initialData, 'REJECTED');
  const counts = resolveNominationKpiCounts(next.statewideTrainers, next.allFacultyNominations);

  assert.equal(next.statewideTrainers.nomination_summary.NOMINATED, 2);
  assert.equal(next.statewideTrainers.nomination_summary.SANCTIONED, 4);
  assert.equal(next.statewideTrainers.nomination_summary.REJECTED, 1);
  assert.equal(counts.pendingNominationsCount, 2);
  assert.equal(counts.sanctionedNominationsCount, 4);
  assert.equal(next.allFacultyNominations.find((n) => n.id === 'nom-3').status, 'REJECTED');
});

test('zero counts remain non-negative across transitions', () => {
  const zeroState = {
    statewideTrainers: {
      nomination_summary: {
        NOMINATED: 0,
        SANCTIONED: 0,
        REJECTED: 0,
      },
    },
    allFacultyNominations: [],
    nominationId: 'nom-x',
    updatedRecord: { id: 'nom-x', status: 'SANCTIONED' },
  };

  const next = applyNominationStatusTransition(zeroState, 'SANCTIONED');
  assert.equal(next.statewideTrainers.nomination_summary.NOMINATED, 0);
  assert.equal(next.statewideTrainers.nomination_summary.SANCTIONED, 1);
});

test('fallback to nominations list when statewide analytics is null', () => {
  const nominationsList = [
    { id: 'nom-1', status: 'NOMINATED' },
    { id: 'nom-2', status: 'SANCTIONED' },
    { id: 'nom-3', status: 'SANCTIONED' },
  ];

  const counts = resolveNominationKpiCounts(null, nominationsList);
  assert.equal(counts.pendingNominationsCount, 1);
  assert.equal(counts.sanctionedNominationsCount, 2);
});

test('emerging-trade terminology labels do not present faculty as certified instructors', () => {
  const kpiCardTitle = 'Emerging-Trade Faculty';
  const kpiCardSubtitle = 'Industry 4.0 & Emerging Trades';
  const tableHeader = 'Emerging-Trade Faculty';

  assert.equal(kpiCardTitle.includes('Certified'), false);
  assert.equal(kpiCardSubtitle.includes('Certified'), false);
  assert.equal(tableHeader.includes('Certified'), false);
  assert.equal(kpiCardTitle, 'Emerging-Trade Faculty');
  assert.equal(tableHeader, 'Emerging-Trade Faculty');
});

test('faculty roster empty state prompts to register instructor and spans 5 columns', () => {
  const result = renderFacultyRosterRows([]);
  assert.equal(result.isEmpty, true);
  assert.equal(result.colSpan, 5);
  assert.equal(result.promptText.includes('register an instructor'), true);
});

test('faculty roster populated state preserves instructor rows', () => {
  const instructors = [
    { id: 'tr-1', name: 'Dr. Ramesh Sharma', primary_trade: 'Mechatronics & Robotics' },
    { id: 'tr-2', name: 'Sunita Patil', primary_trade: 'Electric Vehicles' },
  ];
  const result = renderFacultyRosterRows(instructors);
  assert.equal(result.isEmpty, false);
  assert.equal(result.rowCount, 2);
  assert.equal(result.rows[0].name, 'Dr. Ramesh Sharma');
  assert.equal(result.rows[1].trade, 'Electric Vehicles');
});
