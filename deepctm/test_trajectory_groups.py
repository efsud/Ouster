import copy
import unittest

from .trajectory_groups import TrajectoryGroups, group


def track(obj, lag=0., speed=10., lateral=0., direction="eastbound", movement="WE", points=None):
    sign = 1 if direction == "eastbound" else -1
    return dict(source_key=["session", str(obj), "2"], class_type="2", direction=direction,
                points=points if points is not None else [[lag + i * .5, sign * i * .5 * speed, speed] for i in range(31)],
                lateral_start_m=lateral, lateral_end_m=lateral,
                movement={"movement": movement} if movement else {})


def site(*tracks):
    return dict(id="test-site", name="Test intersection", station_m=0, tracks=list(tracks))


class TrajectoryGroupTests(unittest.TestCase):
    def test_whole_paths_form_supported_cohort_original_indices_preserved(self):
        unsupported = track("noise", lag=300)
        s = site(unsupported, track("a"), track("b", lag=3), track("c", lag=6))
        before = copy.deepcopy(s)
        result = group(s)
        self.assertEqual(s, before)
        self.assertIsNone(result["assignments"][0])
        self.assertEqual(len(result["groups"]), 1)
        g = result["groups"][0]
        self.assertEqual(g["member_indices"], [1, 2, 3])
        self.assertEqual(g["identity_count"], 3)
        self.assertIn(g["medoid_index"], [1, 2, 3])
        self.assertNotIn("points", g)
        self.assertTrue(all(x == g["group_id"] for x in result["assignments"][1:]))

    def test_location_time_speed_direction_and_turn_each_restrict_grouping(self):
        anchor = [track("a"), track("b", lag=3)]
        for other in (track("c", lag=60), track("c", lateral=8), track("c", speed=17),
                      track("c", direction="westbound", movement="EW"), track("c", movement="WN")):
            with self.subTest(other=other):
                self.assertEqual(group(site(*anchor, other))["groups"], [])

    def test_profile_not_only_average_speed(self):
        # Same mean speed, but opposite accelerate/decelerate profiles.
        same = [[i * .5, i * 5., 5. + i / 3.] for i in range(31)]
        different = [[i * .5, i * 5., 15. - i / 3.] for i in range(31)]
        s = site(track("a", points=same), track("b", points=same), track("c", points=different))
        self.assertEqual(group(s)["groups"], [])

    def test_duplicate_fragments_do_not_supply_density(self):
        s = site(track("a"), track("a", lag=.1), track("a", lag=.2), track("b", lag=3))
        self.assertEqual(group(s)["groups"], [])

    def test_class_changes_preserve_local_identity(self):
        a = track("same")
        b = track("same", lag=1)
        b["source_key"][2] = "4"
        b["class_type"] = "4"
        self.assertEqual(group(site(a, b, track("other", lag=3)))["groups"], [])

    def test_missing_identity_or_estimated_track_never_supports_group(self):
        base = [track("a"), track("b", lag=3)]
        for alteration in ({"source_key": []}, {"source": "inferred"}, {"method": "predicted"}):
            c = dict(track("c", lag=6), **alteration)
            self.assertEqual(group(site(*base, c))["groups"], [])

    def test_no_interpolation_across_unobserved_gap(self):
        p = [[0., 0., 10.], [.5, 5., 10.], [10., 100., 10.], [10.5, 105., 10.]]
        s = site(*(track(str(i), points=[[t + i, x, v] for t, x, v in p]) for i in range(3)))
        self.assertEqual(group(s)["groups"], [])

    def test_clock_reordering_not_silently_repaired(self):
        broken = track("c")
        broken["points"][5][0] = 0
        self.assertEqual(group(site(track("a"), track("b", lag=3), broken))["groups"], [])

    def test_density_does_not_chain_through_whole_recording(self):
        result = group(site(*(track(str(i), lag=i * 15) for i in range(15))))
        self.assertGreater(len(result["groups"]), 1)
        for g in result["groups"]:
            self.assertLessEqual(max(g["member_indices"]) - min(g["member_indices"]), 2)

    def test_unknown_turn_cannot_bridge_conflicting_movements(self):
        tracks = [track("u", movement=None), track("a", movement="WE"), track("b", movement="WE"),
                  track("c", movement="WN"), track("d", movement="WN")]
        result = group(site(*tracks))
        for g in result["groups"]:
            self.assertLessEqual(len(g["movement_codes"]), 1)

    def test_stationary_groups_need_shared_time_and_distinct_ids(self):
        result = group(site(*(track(str(i), lag=i, speed=0, points=[[j * .5 + i, i * 5., 0] for j in range(21)]) for i in range(3))))
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["kind"], "stationary_trajectory_cohort")

    def test_visible_target_excludes_every_same_identity_fragment(self):
        target = track("target", lag=2)
        duplicate = track("target", lag=3)
        peers = [track("peer" + str(i), lag=i * 2) for i in range(4)]
        s = site(target, duplicate, *peers)
        masked = copy.deepcopy(target)
        masked["points"] = [p for p in masked["points"] if not 5 < p[0] < 10]
        model = TrajectoryGroups(s)
        assigned = model.classify_visible(masked)
        self.assertIsNotNone(assigned)
        self.assertTrue(all(i >= 2 for i in assigned["donor_indices"]))
        excluded = model.group(("session", "target"))
        self.assertIsNone(excluded["assignments"][0])
        self.assertIsNone(excluded["assignments"][1])

    def test_target_hidden_samples_cannot_change_donor_groups_or_classification(self):
        target = track("target", lag=2)
        peers = [track("peer" + str(i), lag=i * 2) for i in range(4)]
        s = site(target, *peers)
        masked = copy.deepcopy(target)
        masked["points"] = [p for p in masked["points"] if not 5 < p[0] < 10]
        changed = copy.deepcopy(s)
        for p in changed["tracks"][0]["points"]:
            if 5 < p[0] < 10:
                p[1] += 1000
                p[2] = 100
        a, b = TrajectoryGroups(s), TrajectoryGroups(changed)
        self.assertEqual(a.group(("session", "target")), b.group(("session", "target")))
        self.assertEqual(a.classify_visible(masked), b.classify_visible(masked))

    def test_only_two_peer_identities_cannot_classify_target(self):
        target = track("target")
        m = TrajectoryGroups(site(target, track("a", lag=1), track("b", lag=2)))
        self.assertIsNone(m.classify_visible(target))


if __name__ == "__main__":
    unittest.main()
