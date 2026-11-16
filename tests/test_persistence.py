import tempfile, unittest
from pathlib import Path
from yj64_engineering_core.persistence import ProjectStore

class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"projects.sqlite"
        self.store=ProjectStore(self.path)
        self.store.create_project("vessel.demo","Demo vessel")
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def test_snapshot_round_trip_and_reopen(self):
        saved=self.store.save_snapshot("vessel.demo",{"name":"Test","components":[]},expected_revision=0)
        self.assertEqual(saved.revision,1)
        self.store.close()
        with ProjectStore(self.path) as reopened:
            self.assertEqual(reopened.get_snapshot("vessel.demo").payload["name"],"Test")
            self.assertEqual(len(reopened.list_revisions("vessel.demo")),1)
    def test_optimistic_revision_conflict(self):
        self.store.save_snapshot("vessel.demo",{"components":[]},expected_revision=0)
        with self.assertRaisesRegex(RuntimeError,"revision conflict"):
            self.store.save_snapshot("vessel.demo",{"components":[]},expected_revision=0)
    def test_calculation_and_artifact_provenance(self):
        self.store.save_snapshot("vessel.demo",{"components":[{"component_id":"hull","revision":1}]},expected_revision=0)
        calc=self.store.record_calculation(calculation_id="calc.1",project_id="vessel.demo",operation="physics.test",input_digest_sha256="a"*64,result={"stress_pa":42},solver_name="test",solver_version="1.0.0",dependencies=[{"component_id":"hull","revision":1}])
        self.assertEqual(calc.status,"current")
        artifact=self.store.record_artifact(artifact_id="report.1",project_id="vessel.demo",media_type="application/pdf",uri="artifact://report.pdf",calculation_id="calc.1",metadata={"kind":"report"})
        self.assertEqual(artifact.status,"current")
        self.assertEqual(self.store.list_artifacts("vessel.demo")[0].sha256,None)
    def test_component_revision_change_marks_calculation_and_artifact_stale(self):
        self.store.save_snapshot("vessel.demo",{"components":[{"component_id":"hull","revision":1}]},expected_revision=0)
        self.store.record_calculation(calculation_id="calc.1",project_id="vessel.demo",operation="physics.test",input_digest_sha256="b"*64,result={"ok":True},solver_name="test",solver_version="1.0.0",dependencies=[{"component_id":"hull","revision":1}])
        self.store.record_artifact(artifact_id="artifact.1",project_id="vessel.demo",media_type="model/step",uri="artifact://hull.step",calculation_id="calc.1")
        self.store.save_snapshot("vessel.demo",{"components":[{"component_id":"hull","revision":2}]},expected_revision=1)
        self.assertEqual(self.store.list_calculations("vessel.demo")[0].status,"stale")
        self.assertEqual(self.store.list_artifacts("vessel.demo")[0].status,"stale")
    def test_transitive_component_dependency_staleness(self):
        payload={"components":[{"component_id":"hull","revision":2},{"component_id":"beam","revision":1,"dependencies":[{"component_id":"hull","revision":1}]}]}
        self.store.save_snapshot("vessel.demo",payload,expected_revision=0)
        calc=self.store.record_calculation(calculation_id="calc.2",project_id="vessel.demo",operation="fem",input_digest_sha256="c"*64,result={},solver_name="fem",solver_version="1.0.0",dependencies=[{"component_id":"beam","revision":1}])
        self.assertEqual(calc.status,"stale")
    def test_rejects_non_finite_json(self):
        with self.assertRaises(ValueError):
            self.store.save_snapshot("vessel.demo",{"bad":float("nan")},expected_revision=0)
if __name__=="__main__": unittest.main()
