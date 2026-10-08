import test from 'node:test';
import assert from 'node:assert/strict';

function createEmployerFeedbackLogic({
  initialValidations = [],
  api,
}) {
  let validations = [...initialValidations];
  let activeFeedback = null;
  let toast = null;

  const showToast = (type, message) => {
    toast = { type, message };
  };

  const handleAction = async (feedbackId, status, notes = null, prof = null) => {
    let previousValidations = validations;
    validations = validations.map((v) =>
      v.id === feedbackId
        ? {
            ...v,
            status,
            notes: notes !== null ? notes : v.notes,
            proficiency_required: prof !== null ? prof : v.proficiency_required,
          }
        : v
    );

    try {
      await api.submitEmployerFeedback(feedbackId, status, notes, prof);
      showToast('success', `Signal calibrated as ${status.toUpperCase()}`);
      activeFeedback = null;
    } catch (err) {
      validations = previousValidations;
      showToast('error', `Failed to calibrate signal: ${err?.message || 'Server error'}`);
    }
  };

  const handleBatchConfirmFiltered = async (filteredValidations) => {
    const pendingFiltered = filteredValidations.filter((v) => v.status === 'pending');
    if (pendingFiltered.length === 0) {
      showToast('info', 'No pending signals in current filtered view.');
      return;
    }

    const results = await Promise.allSettled(
      pendingFiltered.map((item) => api.submitEmployerFeedback(item.id, 'confirmed'))
    );

    const succeededIds = new Set();
    let failureCount = 0;

    results.forEach((res, idx) => {
      if (res.status === 'fulfilled') {
        succeededIds.add(pendingFiltered[idx].id);
      } else {
        failureCount += 1;
      }
    });

    if (succeededIds.size > 0) {
      validations = validations.map((v) =>
        succeededIds.has(v.id) ? { ...v, status: 'confirmed' } : v
      );
    }

    if (failureCount === 0) {
      showToast('success', `Batch confirmed ${succeededIds.size} industry skill signals!`);
    } else if (succeededIds.size > 0) {
      showToast(
        'error',
        `Confirmed ${succeededIds.size} signals, but ${failureCount} failed to update.`
      );
    } else {
      showToast('error', `Failed to update ${failureCount} skill signals.`);
    }
  };

  return {
    getValidations: () => validations,
    getActiveFeedback: () => activeFeedback,
    setActiveFeedback: (f) => { activeFeedback = f; },
    getToast: () => toast,
    handleAction,
    handleBatchConfirmFiltered,
  };
}

function createCandidateFeedbackLogic({
  initialCandidates = [],
  api,
}) {
  let placedCandidates = [...initialCandidates];
  let activeFeedbackCandidate = null;
  let submittingFeedback = false;
  let toast = null;

  const showToast = (type, message) => {
    toast = { type, message };
  };

  const handleCandidateFeedbackSubmit = async (formData) => {
    if (!activeFeedbackCandidate) return;
    submittingFeedback = true;
    try {
      const res = await api.submitPlacementEmployerFeedback(activeFeedbackCandidate.id, formData);
      if (res?.feedback) {
        showToast('success', 'Workforce feedback recorded! Syllabus blueprints updated.');
        placedCandidates = placedCandidates.map((c) =>
          c.id === activeFeedbackCandidate.id ? { ...c, status: 'FEEDBACK_RECEIVED' } : c
        );
        activeFeedbackCandidate = null;
      } else {
        showToast('error', res?.message || 'Server returned an invalid feedback response.');
      }
    } catch (err) {
      showToast('error', `Failed submitting feedback: ${err?.message || 'Network error'}`);
    } finally {
      submittingFeedback = false;
    }
  };

  return {
    getPlacedCandidates: () => placedCandidates,
    getActiveFeedbackCandidate: () => activeFeedbackCandidate,
    setActiveFeedbackCandidate: (c) => { activeFeedbackCandidate = c; },
    isSubmitting: () => submittingFeedback,
    getToast: () => toast,
    handleCandidateFeedbackSubmit,
  };
}

test('handleAction rolls back optimistic state and emits error toast on API failure', async () => {
  const initial = [
    { id: 'fb-1', status: 'pending', notes: '', proficiency_required: 'intermediate' },
  ];
  const api = {
    submitEmployerFeedback: async () => {
      throw new Error('Database connection failed');
    },
  };

  const logic = createEmployerFeedbackLogic({ initialValidations: initial, api });
  logic.setActiveFeedback(initial[0]);

  await logic.handleAction('fb-1', 'confirmed');

  assert.equal(logic.getValidations()[0].status, 'pending');
  assert.equal(logic.getToast()?.type, 'error');
  assert.match(logic.getToast()?.message, /Failed to calibrate signal/);
  assert.notEqual(logic.getActiveFeedback(), null);
});

test('handleAction commits state and emits success toast on successful API response', async () => {
  const initial = [
    { id: 'fb-1', status: 'pending', notes: '', proficiency_required: 'intermediate' },
  ];
  const api = {
    submitEmployerFeedback: async () => ({ status: 'updated' }),
  };

  const logic = createEmployerFeedbackLogic({ initialValidations: initial, api });
  logic.setActiveFeedback(initial[0]);

  await logic.handleAction('fb-1', 'confirmed');

  assert.equal(logic.getValidations()[0].status, 'confirmed');
  assert.equal(logic.getToast()?.type, 'success');
  assert.match(logic.getToast()?.message, /Signal calibrated as CONFIRMED/);
  assert.equal(logic.getActiveFeedback(), null);
});

test('handleBatchConfirmFiltered confirms all items on full batch success', async () => {
  const items = [
    { id: 'fb-1', status: 'pending' },
    { id: 'fb-2', status: 'pending' },
  ];
  const api = {
    submitEmployerFeedback: async () => ({ status: 'updated' }),
  };

  const logic = createEmployerFeedbackLogic({ initialValidations: items, api });
  await logic.handleBatchConfirmFiltered(items);

  assert.equal(logic.getValidations().every((v) => v.status === 'confirmed'), true);
  assert.equal(logic.getToast()?.type, 'success');
  assert.match(logic.getToast()?.message, /Batch confirmed 2/);
});

test('handleBatchConfirmFiltered updates only succeeded items on partial failure', async () => {
  const items = [
    { id: 'fb-1', status: 'pending' },
    { id: 'fb-2', status: 'pending' },
  ];
  const api = {
    submitEmployerFeedback: async (id) => {
      if (id === 'fb-2') throw new Error('Timeout');
      return { status: 'updated' };
    },
  };

  const logic = createEmployerFeedbackLogic({ initialValidations: items, api });
  await logic.handleBatchConfirmFiltered(items);

  const vals = logic.getValidations();
  assert.equal(vals.find((v) => v.id === 'fb-1')?.status, 'confirmed');
  assert.equal(vals.find((v) => v.id === 'fb-2')?.status, 'pending');
  assert.equal(logic.getToast()?.type, 'error');
  assert.match(logic.getToast()?.message, /Confirmed 1 signals, but 1 failed to update/);
});

test('handleBatchConfirmFiltered emits error toast on complete batch failure', async () => {
  const items = [
    { id: 'fb-1', status: 'pending' },
  ];
  const api = {
    submitEmployerFeedback: async () => {
      throw new Error('Network error');
    },
  };

  const logic = createEmployerFeedbackLogic({ initialValidations: items, api });
  await logic.handleBatchConfirmFiltered(items);

  assert.equal(logic.getValidations()[0].status, 'pending');
  assert.equal(logic.getToast()?.type, 'error');
  assert.match(logic.getToast()?.message, /Failed to update 1 skill signals/);
});

test('candidate feedback handles expected successful response', async () => {
  const candidate = { id: 'cand-1', status: 'PLACED' };
  const api = {
    submitPlacementEmployerFeedback: async () => ({
      feedback: { id: 'pef-1', skill_adequacy_score: 5 },
    }),
  };

  const logic = createCandidateFeedbackLogic({ initialCandidates: [candidate], api });
  logic.setActiveFeedbackCandidate(candidate);

  await logic.handleCandidateFeedbackSubmit({ skill_adequacy_score: 5 });

  assert.equal(logic.getPlacedCandidates()[0].status, 'FEEDBACK_RECEIVED');
  assert.equal(logic.getActiveFeedbackCandidate(), null);
  assert.equal(logic.getToast()?.type, 'success');
  assert.equal(logic.isSubmitting(), false);
});

test('candidate feedback handles unexpected response without feedback payload', async () => {
  const candidate = { id: 'cand-1', status: 'PLACED' };
  const api = {
    submitPlacementEmployerFeedback: async () => ({
      status: 'ok',
    }),
  };

  const logic = createCandidateFeedbackLogic({ initialCandidates: [candidate], api });
  logic.setActiveFeedbackCandidate(candidate);

  await logic.handleCandidateFeedbackSubmit({ skill_adequacy_score: 5 });

  assert.equal(logic.getPlacedCandidates()[0].status, 'PLACED');
  assert.notEqual(logic.getActiveFeedbackCandidate(), null);
  assert.equal(logic.getToast()?.type, 'error');
  assert.match(logic.getToast()?.message, /invalid feedback response/);
  assert.equal(logic.isSubmitting(), false);
});

test('candidate feedback handles network or API exception', async () => {
  const candidate = { id: 'cand-1', status: 'PLACED' };
  const api = {
    submitPlacementEmployerFeedback: async () => {
      throw new Error('Connection refused');
    },
  };

  const logic = createCandidateFeedbackLogic({ initialCandidates: [candidate], api });
  logic.setActiveFeedbackCandidate(candidate);

  await logic.handleCandidateFeedbackSubmit({ skill_adequacy_score: 5 });

  assert.equal(logic.getPlacedCandidates()[0].status, 'PLACED');
  assert.notEqual(logic.getActiveFeedbackCandidate(), null);
  assert.equal(logic.getToast()?.type, 'error');
  assert.match(logic.getToast()?.message, /Failed submitting feedback/);
  assert.equal(logic.isSubmitting(), false);
});
