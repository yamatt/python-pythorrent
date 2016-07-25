import unittest
import pythorrent

def my_module_suite():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_module)
    return suite
