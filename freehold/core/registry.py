from freehold.features.core.feature import CoreFeature
from freehold.features.control.feature import ControlFeature
from freehold.features.arrays.feature import ArraysFeature
from freehold.features.result.feature import ResultFeature
from freehold.features.records.feature import RecordsFeature
from freehold.features.cfg_smt.feature import CfgSmtFeature

class FeatureRegistry:
    def __init__(self):
        self.features = {}
        self.contributions = {}
    def register(self, feature):
        if feature.name in self.features:
            raise ValueError(f"feature already registered: {feature.name}")
        self.features[feature.name] = feature
        self.contributions[feature.name] = feature.contribute()
    def enabled_names(self):
        return list(self.features)

def default_registry():
    reg = FeatureRegistry()
    for f in [CoreFeature(), ControlFeature(), ArraysFeature(), ResultFeature(), RecordsFeature(), CfgSmtFeature()]:
        reg.register(f)
    return reg
