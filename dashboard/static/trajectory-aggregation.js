/* Observed trajectory aggregation. Empty cells are absent, never zero-speed fills. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.TrajectoryAggregation = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  const classes = {
    vehicles: new Set(['1', '2', '3', '4', '5', '6', '7', '8', '9', '15']),
    pedestrians: new Set(['0', '10', '11', '14', '16']),
    cyclists: new Set(['12', '13', '17'])
  };

  /**
   * Points are [window-relative seconds, corridor station metres, speed m/s].
   * Time and space bins are anchored at zero, independent of pan/zoom. Bounds
   * are half-open [start,end); output time edges are clipped to those bounds.
   *
   * Each sensor/session/object contributes one mean speed per occupied cell.
   * Cell speed is the equal-weight mean of those object means, so repeated
   * samples, classifications or fragments do not give one ID extra weight.
   * Repeated timestamps for that object in that cell retain the first sample.
   * Cells from different sensors remain separate, including spatial overlaps.
   * Object counts describe observed local IDs, not traffic flow or density.
   */
  function build(sites, options = {}) {
    const {direction, objects = 'vehicles', timeBinSeconds = 10,
      spaceBinMeters = 10, start = 0, end = 3600} = options;
    if (!Number.isFinite(timeBinSeconds) || timeBinSeconds <= 0 ||
        !Number.isFinite(spaceBinMeters) || spaceBinMeters <= 0 ||
        !Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      throw new RangeError('Finite positive bins and start < end are required.');
    }
    if (objects !== 'all' && !classes[objects]) {
      throw new RangeError('Unknown object filter.');
    }
    const siteBins = new Map();
    const observedIdentities = new Set();
    const summary = {
      cellCount: 0, sampleCount: 0, objectCellCount: 0, sensorObjectCount: 0,
      inputTrackCount: 0, selectedTrackCount: 0, fragmentFallbackTracks: 0,
      duplicateSamples: 0, conflictingDuplicateSamples: 0,
      invalidSamples: 0, outOfWindowSamples: 0,
      timeBinSeconds, spaceBinMeters, start, end, binOrigin: 0,
      estimatedSamplesIncluded: false
    };
    for (const [siteIndex, site] of (sites || []).entries()) {
      const siteId = site.id == null ? `anonymous-site-${siteIndex}` : String(site.id);
      let bins = siteBins.get(siteId);
      if (!bins) { bins = new Map(); siteBins.set(siteId, bins); }
      for (const [trackIndex, tr] of (site.tracks || []).entries()) {
        summary.inputTrackCount++;
        if (tr.method || tr.source === 'inferred' || tr.source === 'estimated') continue;
        if (direction && direction !== 'all' && tr.direction !== direction) continue;
        if (objects !== 'all' && !classes[objects].has(String(tr.class_type))) continue;
        summary.selectedTrackCount++;
        const key = tr.source_key;
        const hasIdentity = Array.isArray(key) && key.length >= 2 &&
          key[0] != null && key[0] !== '' && key[1] != null && key[1] !== '';
        const identity = hasIdentity ? JSON.stringify(['object', key[0], key[1]]) :
          JSON.stringify(['fragment', siteIndex, trackIndex]);
        if (!hasIdentity) summary.fragmentFallbackTracks++;
        let used = false;
        for (const p of tr.points || []) {
          const t = p && p[0], x = p && p[1], speed = p && p[2];
          if (!Number.isFinite(t) || !Number.isFinite(x) ||
              !Number.isFinite(speed) || speed < 0) {
            summary.invalidSamples++; continue;
          }
          if (t < start || t >= end) { summary.outOfWindowSamples++; continue; }
          const ti = Math.floor(t / timeBinSeconds), xi = Math.floor(x / spaceBinMeters);
          const binKey = ti + ':' + xi;
          let bin = bins.get(binKey);
          if (!bin) {
            bin = {site: siteId, ti, xi, objects: new Map()};
            bins.set(binKey, bin);
          }
          let object = bin.objects.get(identity);
          if (!object) {
            object = {sum: 0, count: 0, timestamps: new Map()};
            bin.objects.set(identity, object);
          }
          if (object.timestamps.has(t)) {
            summary.duplicateSamples++;
            if (object.timestamps.get(t) !== speed) summary.conflictingDuplicateSamples++;
            continue;
          }
          object.timestamps.set(t, speed); object.sum += speed; object.count++;
          summary.sampleCount++; used = true;
        }
        if (used) observedIdentities.add(JSON.stringify([siteId, identity]));
      }
    }
    const cells = [];
    for (const bins of siteBins.values()) for (const bin of bins.values()) {
      let sum = 0, sampleCount = 0;
      for (const object of bin.objects.values()) {
        sum += object.sum / object.count; sampleCount += object.count;
      }
      const objectCount = bin.objects.size;
      summary.objectCellCount += objectCount;
      cells.push({site: bin.site,
        timeStart: Math.max(start, bin.ti * timeBinSeconds),
        timeEnd: Math.min(end, (bin.ti + 1) * timeBinSeconds),
        spaceStart: bin.xi * spaceBinMeters, spaceEnd: (bin.xi + 1) * spaceBinMeters,
        speed: sum / objectCount, objectCount, sampleCount});
    }
    cells.sort((a, b) => a.timeStart - b.timeStart || a.spaceStart - b.spaceStart ||
      a.site.localeCompare(b.site));
    summary.cellCount = cells.length;
    summary.sensorObjectCount = observedIdentities.size;
    return {cells, summary};
  }
  return {build};
});
