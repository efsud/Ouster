'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {build} = require('../static/trajectory-aggregation.js');

function track(id, points, extra = {}) {
  return {source_key: ['s', id, '2'], class_type: '2', direction: 'eastbound', points, ...extra};
}
function site(id, tracks) { return {id, tracks}; }
const options = {direction: 'eastbound', objects: 'vehicles', end: 60};

test('each observed object has equal weight regardless of sampling frequency', () => {
  const a = track('a', [[0, 1, 0], [1, 1, 0], [2, 1, 0], [3, 1, 0]]);
  const b = track('b', [[1, 2, 20]]);
  const result = build([site('A', [a, b])], options);
  assert.equal(result.cells[0].speed, 10);
  assert.equal(result.cells[0].objectCount, 2);
  assert.equal(result.cells[0].sampleCount, 5);
});

test('classification changes and fragments retain local identity and deduplicate timestamps', () => {
  const a = track('a', [[0, 1, 10], [1, 2, 20]]);
  const b = track('a', [[1, 2, 20], [2, 3, 30]], {class_type: '4', source_key: ['s', 'a', '4']});
  const input = [site('A', [a, b])];
  const unchanged = JSON.stringify(input);
  const r = build(input, options);
  assert.equal(r.cells[0].speed, 20);
  assert.equal(r.cells[0].objectCount, 1);
  assert.equal(r.cells[0].sampleCount, 3);
  assert.equal(r.summary.duplicateSamples, 1);
  assert.equal(r.summary.sensorObjectCount, 1);
  assert.equal(JSON.stringify(input), unchanged);
});

test('same ID across sensors or sessions does not establish shared vehicle identity', () => {
  const input = [site('A', [track('a', [[1, 1, 4]]),
    track('a', [[1, 1, 8]], {source_key: ['other-session', 'a', '2']})]),
    site('B', [track('a', [[1, 1, 20]])])];
  const r = build(input, options);
  assert.equal(r.cells.length, 2);
  assert.equal(r.cells.find(c => c.site === 'A').speed, 6);
  assert.equal(r.cells.find(c => c.site === 'B').speed, 20);
  assert.equal(r.summary.sensorObjectCount, 3);
});

test('only observations in the chosen direction and object group contribute', () => {
  const input = [site('A', [track('car', [[1, 1, 10]]),
    track('reverse', [[1, 1, 15]], {direction: 'westbound'}),
    track('pedestrian', [[1, 1, 1]], {class_type: '10'}),
    track('cyclist', [[1, 1, 5]], {class_type: '12'}),
    track('estimate', [[1, 1, 100]], {method: 'prediction'}),
    track('inferred', [[1, 1, 100]], {source: 'inferred'})])];
  assert.equal(build(input, options).cells[0].speed, 10);
  assert.equal(build(input, {...options, objects: 'pedestrians'}).cells[0].speed, 1);
  assert.equal(build(input, {...options, objects: 'cyclists'}).cells[0].speed, 5);
  assert.equal(build(input, {...options, direction: 'westbound'}).cells[0].speed, 15);
  assert.equal(build(input, {...options, objects: 'all'}).cells[0].objectCount, 3);
});

test('missing cells stay absent while observed stopped traffic has zero speed', () => {
  const r = build([site('A', [track('a', [[1, 1, 0], [41, 51, 10]])])], options);
  assert.equal(r.cells.length, 2);
  assert.equal(r.cells[0].speed, 0);
  assert.deepEqual(r.cells.map(c => c.timeStart), [0, 40]);
  assert.deepEqual(r.cells.map(c => c.spaceStart), [0, 50]);
});

test('bins stay zero-anchored, boundaries are half-open, bounds clip only time edges', () => {
  const input = [site('A', [track('a', [[0, -1, 1], [8, -1, 2], [10, 0, 3], [20, 10, 4]])])];
  const r = build(input, {...options, start: 5, end: 20});
  assert.deepEqual(r.cells.map(c => [c.timeStart, c.timeEnd, c.spaceStart, c.spaceEnd]),
    [[5, 10, -10, 0], [10, 20, 0, 10]]);
  assert.equal(r.summary.outOfWindowSamples, 2);
});

test('missing identity does not merge unrelated fragments and invalid points are excluded', () => {
  const r = build([site('A', [track('a', [[1, 1, 4]], {source_key: null}),
    track('b', [[1, 1, 8], [2, 1, NaN], [3, Infinity, 1], [4, 1, -1]], {source_key: null})])], options);
  assert.equal(r.cells[0].objectCount, 2);
  assert.equal(r.cells[0].speed, 6);
  assert.equal(r.summary.fragmentFallbackTracks, 2);
  assert.equal(r.summary.invalidSamples, 3);
});

test('conflicting duplicate timestamp is disclosed and cannot increase observation weight', () => {
  const r = build([site('A', [track('a', [[1, 1, 3], [1, 1, 20]])])], options);
  assert.equal(r.cells[0].speed, 3);
  assert.equal(r.cells[0].sampleCount, 1);
  assert.equal(r.summary.conflictingDuplicateSamples, 1);
});

test('invalid configuration is rejected', () => {
  assert.throws(() => build([], {...options, timeBinSeconds: 0}), RangeError);
  assert.throws(() => build([], {...options, start: 60}), RangeError);
  assert.throws(() => build([], {...options, objects: 'typo'}), RangeError);
});
