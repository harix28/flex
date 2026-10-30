import numpy as np
import pytest
from sentinel.classification import LifetimeClassifier, TRUSTED_MANIFEST
from sentinel.config import ROOT
from sentinel.data import read_data, SETTINGS, SENSORS
from sentinel.all_subsets_training import forest_predict, RAW_FEATURES

ARTIFACT = ROOT / 'runs/all-subsets-20261030-v1/COMBINED'

@pytest.fixture(scope='module')
def classifier():
    if not ARTIFACT.exists():
        pytest.skip('Trusted offline RF artifact not installed')
    return LifetimeClassifier(ARTIFACT)

def test_real_observations_match_offline_model(classifier):
    for subset in ('FD001', 'FD002', 'FD003', 'FD004'):
        frame = read_data(ROOT / f'data/raw/test_{subset}.txt').iloc[:15]
        expected = forest_predict(ARTIFACT, frame[RAW_FEATURES], TRUSTED_MANIFEST)
        actual = [classifier.predict(int(r.cycle), r[SETTINGS].tolist(),
                  r[SENSORS].tolist()) for _,r in frame.iterrows()]
        np.testing.assert_array_equal(actual, expected)

@pytest.mark.parametrize('cycle,settings,sensors', [
    (0,[0]*3,[0]*21), (True,[0]*3,[0]*21), (1,[0]*2,[0]*21),
    (1,[0]*3,[float('nan')]*21), (1,[float('inf')]*3,[0]*21),
])
def test_invalid_input(classifier, cycle, settings, sensors):
    with pytest.raises(ValueError):
        classifier.predict(cycle, settings, sensors)

def test_untrusted_manifest_rejected(tmp_path):
    (tmp_path/'forest.json').write_text('{}')
    with pytest.raises(ValueError, match='manifest rejected'):
        LifetimeClassifier(tmp_path)
