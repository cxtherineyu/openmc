import os
import h5py

import numpy as np
import pytest
import openmc

from tests.testing_harness import PyAPITestHarness


@pytest.fixture
def model(request):
    marker = request.node.get_closest_marker("surf_src_op")
    surf_src_op = marker.args[0]

    openmc_model = openmc.model.Model()

    # Materials
    # None

    # Geometry
    # Concentric void spheres
    # - Innermost sphere to bank surface sources
    # - Second shell to tally cell flux
    # - Outermost sphere as vacuum boundary
    sph_1 = openmc.Sphere(r=1.0, surface_id=1)  # Surface to bank/write sources.
    sph_2 = openmc.Sphere(r=2.0, surface_id=2)
    sph_3 = openmc.Sphere(r=2.5, surface_id=3)
    sph_4 = openmc.Sphere(r=4.0, surface_id=4, boundary_type='vacuum')
    cell_1 = openmc.Cell(1, region=-sph_1)
    cell_2 = openmc.Cell(2, region=+sph_1&-sph_2)
    cell_3 = openmc.Cell(3, region=+sph_2&-sph_3)  # Cell to tally flux.
    cell_4 = openmc.Cell(4, region=+sph_3&-sph_4)
    root = openmc.Universe(universe_id=1,
                           cells=[cell_1, cell_2, cell_3, cell_4])
    openmc_model.geometry = openmc.Geometry(root)

    # Settings
    openmc_model.settings.run_mode = 'fixed source'
    openmc_model.settings.particles = 1000
    openmc_model.settings.batches = 10
    openmc_model.settings.seed = 1

    if surf_src_op == 'write':
        point = openmc.stats.Point((0, 0, 0))
        pt_src = openmc.Source(space=point)
        openmc_model.settings.source = pt_src

        openmc_model.settings.surf_src_write = {'surf_ids': [1],
                                                'max_surf_banks': 1000}
    elif surf_src_op == 'read':
        openmc_model.settings.surf_src_read = {'path': 'surface_source_true.h5'}

    # Tallies
    tal = openmc.Tally(1)
    cell_filter = openmc.CellFilter(cell_3, 1)
    tal.filters = [cell_filter]
    tal.scores = ['flux']
    openmc_model.tallies.append(tal)

    return openmc_model


class SurfaceSourceTestHarness(PyAPITestHarness):
    def _test_output_created(self):
        """Make sure surface_source.h5 has also been created."""
        super()._test_output_created()
        # Check if 'surface_source.h5' has been created.
        if self._model.settings.surf_src_write:
            assert os.path.exists('surface_source.h5'), \
                'Surface source file does not exist.'

    def _compare_output(self):
        """Make sure the current surface_source.h5 agree with the reference."""
        if self._model.settings.surf_src_write:
            with h5py.File("surface_source_true.h5", 'r') as f:
                src_true = f['source_bank'][()]
            with h5py.File("surface_source.h5", 'r') as f:
                src_test = f['source_bank'][()]
            np.testing.assert_array_equal(np.sort(src_true), np.sort(src_test))

    def execute_test(self):
        """Build input XMLs, run OpenMC, check output and results."""
        try:
            self._build_inputs()
            inputs = self._get_inputs()
            self._write_inputs(inputs)
            self._compare_inputs()
            self._run_openmc()
            self._test_output_created()
            self._compare_output()
            results = self._get_results()
            self._write_results(results)
            self._compare_results()
        finally:
            self._cleanup()

    def _cleanup(self):
        """Delete statepoints, tally, and test files."""
        super()._cleanup()
        fs = 'surface_source.h5'
        if os.path.exists(fs):
            os.remove(fs)


@pytest.mark.surf_src_op('write')
def test_surface_source_write(model):
    harness = SurfaceSourceTestHarness('statepoint.10.h5',
                                       model,
                                       'inputs_true_write.dat')
    harness.main()


@pytest.mark.surf_src_op('read')
def test_surface_source_read(model):
    harness = SurfaceSourceTestHarness('statepoint.10.h5',
                                       model,
                                       'inputs_true_read.dat')
    harness.main()
