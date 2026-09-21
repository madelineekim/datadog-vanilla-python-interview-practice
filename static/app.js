const notice = document.querySelector('#notice');
async function api(path, method = 'GET', body) {
  const response = await fetch(path, {method, headers: body ? {'Content-Type': 'application/json'} : {}, body: body ? JSON.stringify(body) : undefined});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  return result;
}
function report(error) { notice.textContent = error.message; }
async function refresh() {
  const data = await api('/api/services?limit=100');
  const container = document.querySelector('#services');
  container.replaceChildren();
  notice.textContent = `Showing ${data.items.length} of ${data.total} services`;
  for (const service of data.items) {
    const article = document.createElement('article');
    const title = document.createElement('h2');
    title.textContent = service.name;
    const tags = document.createElement('p');
    tags.textContent = service.tags.join(', ');
    const output = document.createElement('pre');
    const base = `/api/services/${service.id}`;
    const summary = document.createElement('button');
    summary.textContent = 'View summary';
    summary.onclick = async () => { try { output.textContent = JSON.stringify(await api(base + '/summary'), null, 2); } catch (e) { report(e); } };
    article.append(title, tags, summary);
    for (const status of ['ok', 'warning', 'critical']) {
      const button = document.createElement('button');
      button.textContent = `Record ${status}`;
      button.onclick = async () => {
        try {
          await api(base + '/events', 'POST', {events: [{status, latency_ms: 100, message: 'Manual check'}]});
          output.textContent = JSON.stringify(await api(base + '/summary'), null, 2);
        } catch (e) { report(e); }
      };
      article.append(button);
    }
    article.append(output);
    container.append(article);
  }
}
document.querySelector('#register').onsubmit = async event => {
  event.preventDefault();
  try {
    await api('/api/services', 'POST', {name: document.querySelector('#name').value, tags: document.querySelector('#tags').value.split(',').map(s => s.trim()).filter(Boolean)});
    event.target.reset();
    await refresh();
  } catch (e) { report(e); }
};
document.querySelector('#refresh').onclick = () => refresh().catch(report);
refresh().catch(report);
