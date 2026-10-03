# SPDX-License-Identifier: GPL-3.0-only
import copy
import json
from pathlib import Path
import tempfile
import unittest
from handtracking.ai.validate_models import validate,load

ROOT=Path(__file__).resolve().parents[3]/'analysis/builds/52168470052900520'


class EvidenceValidationTests(unittest.TestCase):
    def setUp(self):
        self.models=json.loads((ROOT/'ptez-report.json').read_text())
        self.reference=json.loads((ROOT/'reference-schema-report.json').read_text())

    def test_captured_evidence_is_not_runtime_success(self):
        result=validate(self.models,self.reference)
        self.assertEqual(result['model_count'],10)
        self.assertEqual(result['scalar_count'],35)
        self.assertEqual(result['strict_extent_warnings'],13)
        self.assertFalse(result['horizon_ported'])
        self.assertFalse(result['camera_conversion_validated'])

    def test_missing_duplicate_and_failed_models_are_not_green(self):
        for mutate in (lambda r:r['models'].pop(),
                       lambda r:r['models'].append(copy.deepcopy(r['models'][0])),
                       lambda r:r['models'][0].update(status='DECOMPRESSION_FAILED')):
            report=copy.deepcopy(self.models);mutate(report)
            with self.assertRaises(ValueError):validate(report,self.reference)

    def test_native_rejection_hash_mismatch_and_false_execution_claim(self):
        for field,value in (('public_schema_verifier_passed',False),('decoded_sha256','0'*64),
                            ('model_executed',True)):
            report=copy.deepcopy(self.reference);report['models'][0][field]=value
            with self.assertRaises(ValueError):validate(self.models,report)

    def test_attribute_failure_and_wrong_frontend_are_not_accepted(self):
        report=copy.deepcopy(self.models)
        report['models'][0]['serialized_attributes']['status']='ATTRIBUTES_NOT_RECOVERED'
        with self.assertRaises(ValueError):validate(report,self.reference)
        report=copy.deepcopy(self.models)
        report['models'][0]['serialized_attributes']['attributes']['use_uint8_input']=True
        with self.assertRaises(ValueError):validate(report,self.reference)

    def test_scalar_disagreement_or_missing_crosschecks_rejected(self):
        for mutation in ('missing','disagreement','value'):
            report=copy.deepcopy(self.reference)
            row=next(r for r in report['models'] if r['scalar_crosschecks'])
            if mutation=='missing':row['scalar_crosschecks'].pop()
            elif mutation=='disagreement':row['scalar_crosschecks'][0]['status']='DISAGREEMENT'
            else:row['scalar_crosschecks'][0]['native_int64']+=1
            with self.assertRaises(ValueError):validate(self.models,report)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'report.json';path.write_text('{"status":false,"status":true}')
            with self.assertRaises(ValueError):load(path)
