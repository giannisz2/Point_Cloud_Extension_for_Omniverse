import carb.events
import omni.kit.app
import omni.ext
import omni.ui as ui
import numpy as np
import logging
from pxr import Usd, UsdGeom, Gf
import netCDF4 as nc
from pxr import Gf, Vt
import random
import time

# Setup logging
logging.basicConfig(level=logging.WARNING)

class CompanyPointCloudExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[company.point.cloud] company point cloud startup")

        self._window = ui.Window("Point Cloud Window", width=300, height=300)
        self._first_poll = 0
        self._current_file_index = 0
        self._last_x = 0
        self._last_z = 0
        self._last_num_points = 0
        self._update_timer = 0  # Timer for controlling update frequency
        self._update_interval = 1  # Update every 10 seconds
        self._active_point_cells = set()  # Track (i, j) of active grid cells

        with self._window.frame:
            with ui.VStack():
                ui.Label("Load NetCDF Point Cloud")

                with ui.HStack():
                    ui.Button("Load NetCDF", clicked_fn=self.load_netcdf_point_cloud)

        # Subscribe to the update event stream
        self._update_stream = omni.kit.app.get_app().get_update_event_stream()
        self._update_sub = self._update_stream.create_subscription_to_pop(self._on_update, name="PointCloudUpdate")

    def on_shutdown(self):
        print("[company.point.cloud] company point cloud shutdown")
        # Unsubscribe from the update event stream
        if self._update_sub:
            self._update_sub.unsubscribe()

    def _on_update(self, e: carb.events.IEvent):
        """
        Called on every frame update.
        """
        dt = e.payload["dt"]  # Time elapsed since the last frame (in seconds)
        self._update_timer += dt  # Accumulate elapsed time

        # Update every `_update_interval` seconds
        if self._update_timer >= self._update_interval:
            self._update_timer = 0  # Reset the timer
            self.load_netcdf_point_cloud()  # Load new data

    def add_point_cloud_in_grid(self, x, z, gas_concentration):
        """
        Create a grid system centered at (0, 0, 0) with an area of 1500 x 1500 meters.
        Add multiple points to a cell based on a gas concentration value.
        Uses LOD (Level of Detail) based on camera distance.
        """



        # Grid parameters
        world_size_x = 150  # meters
        world_size_z = 150  # meters
        cell_size = 10       # meters
        half_world_x = world_size_x / 2
        half_world_z = world_size_z / 2

        # Convert world coordinates (x, z) to grid cell (i, j)
        i = int((x + half_world_x) / cell_size) - int(world_size_x / (2 * cell_size))
        j = int((z + half_world_z) / cell_size) - int(world_size_z / (2 * cell_size))

        # Validate cell coordinates
        if i is None or j is None:
            raise ValueError("World coordinates (x, z) must be provided.")

        # Get the current USD stage
        stage = omni.usd.get_context().get_stage()
        if not stage:
            raise RuntimeError("Failed to get the current USD stage.")

        # Get camera transform
        camera_path = "/OmniverseKit_Persp"  # Default for Omniverse Kit
        camera = UsdGeom.Camera.Get(stage, camera_path)
        if not camera:
            raise RuntimeError("Camera not found in USD stage.")

        time = Usd.TimeCode.Default()
        cam_transform = camera.ComputeLocalToWorldTransform(time)
        cam_position = Gf.Vec3f(cam_transform.ExtractTranslation())  # Convert to Vec3f

        # Compute distance from camera to the grid cell
        cell_center = Gf.Vec3f(x, 100, z)
        distance = (cam_position - cell_center).GetLength()

        # Determine LOD factor based on distance for performance optimization
        if distance < 100:
            lod_factor = 1.0  # Full detail (100% points)
        elif distance < 300:
            lod_factor = 0.5  # Medium detail (50% points)
        else:
            lod_factor = 0.1  # Low detail (10% points)

        # Calculate number of points based on gas concentration and LOD factor
        num_points = int(gas_concentration * 50 * lod_factor)
        num_points = max(1, num_points)  # At least one point

        #logging.warning(f"Adding {num_points} points to cell ({i}, {j}) where LOD is {lod_factor}")

        # Define the bounds of the cell
        cell_min_x = x - (cell_size / 2)
        cell_max_x = x + (cell_size / 2)
        cell_min_z = z - (cell_size / 2)
        cell_max_z = z + (cell_size / 2)

        # Add points to the cell
        for point_index in range(num_points):
            point_x = random.uniform(cell_min_x, cell_max_x)
            point_z = random.uniform(cell_min_z, cell_max_z)

            point_path = f"/World/Point_{i}_{j}_{point_index}"
            point = UsdGeom.Sphere.Define(stage, point_path)
            if not point:
                raise RuntimeError(f"Failed to create point at path: {point_path}")

            point.CreateRadiusAttr(0.1)  # Small point size

            # Set position using an existing translate operation
            xformable = UsdGeom.Xformable(point)
            translate_op = None
            for op in xformable.GetOrderedXformOps():
                if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                    translate_op = op
                    break
            if translate_op is None:
                translate_op = xformable.AddTranslateOp()

            translate_op.Set(Gf.Vec3f(point_x, 0, point_z))

            # Set point color (white for now)
            color = self.concentration_to_color(gas_concentration)
            point.CreateDisplayColorAttr(Vt.Vec3fArray([color]))
            self._active_point_cells.add((i, j))

        return i, j


    def concentration_to_color(self, conc, max_conc=1.0):
        """ Maps concentration (0 to max_conc) to RGB color. """
        norm = min(conc / max_conc, 1.0)

        if norm < 0.5:
            # Blue → Green
            t = norm / 0.5
            return Gf.Vec3f(0.0, t, 1.0 - t)
        else:
            # Green → Red
            t = (norm - 0.5) / 0.5
            return Gf.Vec3f(t, 1.0 - t, 0.0)
    
    def remove_all_point_clouds(self):
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return

        for (i, j) in self._active_point_cells:
            for point_index in range(200):
                point_path = f"/World/Point_{i}_{j}_{point_index}"
                prim = stage.GetPrimAtPath(point_path)
                if prim and prim.IsValid():
                    stage.RemovePrim(point_path)

        #logging.warning(f"Removed {len(self._active_point_cells)} cells' points")
        self._active_point_cells.clear()


    def load_netcdf_point_cloud(self):
        """ Load data from NetCDF file using netCDF4 and process all lat/lon dimensions. """
        file_path = f"C:/Users/pcomp/Documents/thesis-flexpart2025-main/output_concentrations_{self._current_file_index:02d}.nc"
        #logging.warning(file_path)
        self.remove_all_point_clouds()  # 🧹 Clear previous points


        try:
            # Open the NetCDF file
            dataset = nc.Dataset(file_path, mode="r")

            # Extract the 'concentrations' variable
            concentrations = dataset.variables["concentrations"]
            gas_concentration = concentrations[:]

            # Close the dataset
            dataset.close()

            # Iterate over all lat/lon dimensions in 150 x 150 values
            for x in range(150):
                for z in range(150):
                    conc = gas_concentration[x, z]
                    if conc == 0:
                        continue

                    # Call grid_manager for this lat/lon pair and concentration
                    self.add_point_cloud_in_grid(x, z, conc)
            
            # Increment the file index for the next iteration
            self._current_file_index = (self._current_file_index + 1) % 12  # Cycle from 00 to 11

        except Exception as e:
            logging.error(f"Failed to load .nc file: {e}")
