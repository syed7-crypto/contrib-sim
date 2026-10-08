const form = document.querySelector('#analysis-form');
const button = document.querySelector('#analyze-button');
const message = document.querySelector('#form-message');
const loading = document.querySelector('#loading');
const errorBox = document.querySelector('#error');
const errorMessage = document.querySelector('#error-message');
const results = document.querySelector('#results');

const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
const list = (items, empty = 'No items returned.') => Array.isArray(items) && items.length
  ? `<ul>${items.map((item) => `<li>${escapeHtml(typeof item === 'string' ? item : JSON.stringify(item))}</li>`).join('')}</ul>`
  : `<p class="empty">${escapeHtml(empty)}</p>`;
const field = (title, content, tone = '') => `<div class="field ${tone}"><h3>${escapeHtml(title)}</h3>${content}</div>`;

function renderPlan(plan = {}) {
  const understanding = plan.issue_understanding || {};
  const files = Array.isArray(plan.relevant_files) ? plan.relevant_files : [];
  const tests = Array.isArray(plan.tests) ? plan.tests : [];
  document.querySelector('#plan-content').innerHTML = [
    field('Issue understanding', `<p>${escapeHtml(understanding.summary || 'No summary returned.')}</p><p>${escapeHtml(understanding.expected_behavior || 'No expected behavior returned.')}</p>${list(understanding.acceptance_criteria, 'No acceptance criteria returned.')}`),
    field('Relevant files', files.length ? files.map((item) => `<div class="file"><div><div class="mono">${escapeHtml(item.path)}</div><p>${escapeHtml(item.reason)}</p></div></div>`).join('') : '<p class="empty">No relevant files returned.</p>', 'green'),
    field('Implementation approach', list(plan.implementation_approach)),
    field('Tests', tests.length ? tests.map((item) => `<div class="file"><div><div class="mono">${escapeHtml(item.path)}</div><p>${escapeHtml(item.purpose)}</p><p>${escapeHtml(item.change)}</p></div></div>`).join('') : '<p class="empty">No tests returned.</p>', 'green'),
    field('Risks & unknowns', list(plan.risks_unknowns), 'amber'),
    field('Contributor checklist', list(plan.contributor_checklist))
  ].join('');
}

function renderGrounding(grounding = {}) {
  const criteria = grounding.acceptance_criteria || {};
  document.querySelector('#grounding-status').textContent = grounding.status || 'unknown';
  document.querySelector('#grounding-content').innerHTML = [
    field('Validated files', list(grounding.validated_files, 'No files were validated.'), 'green'),
    field('Unsupported claims', list(grounding.unsupported_claims, 'No unsupported claims.'), grounding.unsupported_claims?.length ? 'red' : 'green'),
    field('Unverified assumptions', list(grounding.unverified_assumptions, 'No unverified assumptions.'), grounding.unverified_assumptions?.length ? 'amber' : 'green'),
    field('Acceptance criteria · explicit in issue', list(criteria.explicit_in_issue, 'None returned.')),
    field('Acceptance criteria · inferred by model', list(criteria.inferred_by_model, 'None returned.'), 'amber')
  ].join('');
}

function renderReview(review = {}) {
  document.querySelector('#readiness-score').textContent = review.readiness_score == null ? '—' : `${review.readiness_score}/100`;
  const groups = [['Strengths', review.strengths, 'green'], ['Issues', review.issues, 'red'], ['Missing steps', review.missing_steps, 'amber'], ['Test gaps', review.test_gaps, 'red'], ['Grounding concerns', review.grounding_concerns, 'amber'], ['Recommendations', review.recommendations, 'green']];
  document.querySelector('#review-content').innerHTML = `<div class="field green"><h3>Overall status</h3><p class="mono">${escapeHtml(review.overall_status || 'unknown')}</p></div>` + groups.map(([title, values, tone]) => `<div class="review-group"><h3>${escapeHtml(title)}</h3>${list(values)}</div>`).join('');
}

function showError(text) { errorMessage.textContent = text; errorBox.classList.remove('hidden'); }

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  results.classList.add('hidden'); errorBox.classList.add('hidden'); loading.classList.remove('hidden');
  button.disabled = true; message.textContent = 'Collecting repository evidence…';
  document.querySelector('#status-badge').textContent = 'Running';
  try {
    const response = await fetch('/api/analyze', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ repository_url: document.querySelector('#repository-url').value.trim(), issue_url: document.querySelector('#issue-url').value.trim() }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'The analysis request failed.');
    renderPlan(payload.contributor_plan); renderGrounding(payload.grounding); renderReview(payload.review);
    document.querySelector('#repo-label').textContent = document.querySelector('#repository-url').value.trim();
    document.querySelector('#status-badge').textContent = payload.review?.overall_status || 'Complete';
    message.textContent = 'Analysis complete.'; results.classList.remove('hidden'); results.scrollIntoView({behavior: 'smooth'});
  } catch (error) { showError(error.message); message.textContent = 'Try again after checking the URLs and backend status.'; document.querySelector('#status-badge').textContent = 'Error'; }
  finally { loading.classList.add('hidden'); button.disabled = false; }
});

document.querySelector('#theme-button').addEventListener('click', () => document.documentElement.classList.toggle('dark'));
