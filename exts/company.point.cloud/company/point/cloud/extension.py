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
        self._update_interval = 10.0  # Update every 10 seconds

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
        """
        if self._first_poll:
            self.remove_points(self._last_x, self._last_z, self._last_num_points)
            logging.warning(f"Remove points called with {self._last_x}, {self._last_z}, {self._last_num_points}")
        self._first_poll = 1    

        # Grid parameters
        world_size_x = 1500  # meters
        world_size_z = 1500  # meters
        cell_size = 10       # meters
        half_world_x = world_size_x / 2  # The world spans from -750 to +750 meters along X.
        half_world_z = world_size_z / 2  # The world spans from -750 to +750 meters along Z.

        # Convert world coordinates (x, z) to cell coordinates (i, j)
        i = int((float(x) + half_world_x) / cell_size) - int(world_size_x / (2 * cell_size))
        j = int((float(z) + half_world_z) / cell_size) - int(world_size_z / (2 * cell_size))

        # Validate cell coordinates
        if i is None or j is None:
            raise ValueError("World coordinates (x, z) must be provided for 'place_point' action.")

        # Get the current USD stage
        stage = omni.usd.get_context().get_stage()
        if not stage:
            raise RuntimeError("Failed to get the current USD stage.")

        # Calculate the number of points based on gas concentration
        num_points = int(gas_concentration * 100)  # Example: 3.89 → 389 points
        logging.warning(f"Adding {num_points} points to cell ({i}, {j})")

        # Define the bounds of the cell
        cell_min_x = x - (cell_size / 2)
        cell_max_x = x + (cell_size / 2)
        cell_min_z = z - (cell_size / 2)
        cell_max_z = z + (cell_size / 2)

        # Add points to the cell
        for point_index in range(num_points):
            # Generate random coordinates within the cell
            point_x = random.uniform(cell_min_x, cell_max_x)
            point_z = random.uniform(cell_min_z, cell_max_z)

            # Define a point at the random coordinates
            point_path = f"/World/Point_{i}_{j}_{point_index}"
            point = UsdGeom.Sphere.Define(stage, point_path)
            if not point:
                raise RuntimeError(f"Failed to create point at path: {point_path}")

            # Set the radius of the point
            point.CreateRadiusAttr(0.1)  # Smaller radius for multiple points

            # Check if the point already has a translate operation
            xformable = UsdGeom.Xformable(point)
            translate_op = None
            for op in xformable.GetOrderedXformOps():
                if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                    translate_op = op
                    break

            # If no translate operation exists, add one
            if translate_op is None:
                translate_op = xformable.AddTranslateOp()

            # Set the position using random coordinates
            translate_op.Set(Gf.Vec3f(point_x, 0, point_z))

            # Add color to the point (RGB values in the range [0, 1])
            color = Gf.Vec3f(1.0, 1.0, 1.0)
            point.CreateDisplayColorAttr(Vt.Vec3fArray([color]))

        logging.warning(f"Added {num_points} points to cell ({i}, {j})")
        self._last_x = i
        self._last_z = j
        self._last_num_points = num_points
        return i, j

    def remove_points(self, x, z, num_points=380):
        """ Remove points from the USD stage that were created by the grid_manager function. """
        # Get the current USD stage
        stage = omni.usd.get_context().get_stage()
        if not stage:
            raise RuntimeError("Failed to get the current USD stage.")

        # Iterate through the points and remove them
        for point_index in range(num_points):
            # Path of the point
            point_path = f"/World/Point_{x}_{z}_{point_index}"

            # Check if the point exists
            point_prim = stage.GetPrimAtPath(point_path)
            if point_prim.IsValid():
                # Remove the point
                stage.RemovePrim(point_path)
                logging.warning(f"Point at path {point_path} removed.")
            else:
                logging.warning(f"Point at path {point_path} does not exist.")

        print(f"Removed {num_points} points from cell ({x}, {z})")

    def load_netcdf_point_cloud(self):
        """ Load data from NetCDF file using netCDF4 and process all lat/lon dimensions. """
        file_path = f"C:/Users/ov-user/Documents/output_concentrations_{self._current_file_index:02d}.nc"
        logging.warning(file_path)

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
