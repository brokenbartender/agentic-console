"""
Dependency injection container placeholder.
Phase 1: keep minimal; actual wiring added later.
"""

class Container:
    def __init__(self):
        self._services = {}

    def register(self, name, instance):
        self._services[name] = instance

    def get(self, name):
        return self._services.get(name)
