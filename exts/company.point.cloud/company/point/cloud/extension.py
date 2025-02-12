import omni.ext
import omni.ui as ui
import numpy as np
from pxr import Usd, UsdGeom, Gf

class CompanyPointCloudExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[company.point.cloud] company point cloud startup")
        
        # Initialize window and counter
        self._count = 0
        self._created_point_clouds = []  # List to keep track of created point clouds
        self._window = ui.Window("Point Cloud Window", width=300, height=300)
        
        with self._window.frame:
            with ui.VStack():
                label = ui.Label(f"Point Cloud Count: {self._count}")

                with ui.HStack():
                    ui.Button("Create Multiple Point Clouds", clicked_fn=self.create_multiple_point_clouds)
                    ui.Button("Remove Point Clouds", clicked_fn=self.remove_point_clouds)

    def on_shutdown(self):
        print("[company.point.cloud] company point cloud shutdown")

    def create_multiple_point_clouds(self):
        """ Create multiple point clouds at different locations """
        num_points = 1000
        num_clouds = 100  # Number of point clouds to create
        offsets = np.random.uniform(-1000, 1000, size=(num_clouds, 3))  # Random locations for each point cloud

        # Create the stage for USD
        stage = omni.usd.get_context().get_stage()
        
        for i in range(num_clouds):
            # Generate random points for this point cloud
            x = np.random.uniform(-50, 50, num_points)
            y = np.random.uniform(-50, 50, num_points)
            z = np.random.uniform(0, 100, num_points)
            coordinates = np.vstack([x, y, z]).T
            
            # Simulate gas concentration (values between 0 and 1)
            concentration = np.random.uniform(0, 1, num_points)
            
            # Color points based on concentration (blue to red scale)
            colors = np.stack([1 - concentration, np.zeros_like(concentration), concentration], axis=-1)

            # Define unique transform for this point cloud (position offset)
            xform = UsdGeom.Xform.Define(stage, f'/PointCloud_{i}')
            translation = Gf.Vec3f(offsets[i][0], offsets[i][1], offsets[i][2])
            xform.AddTranslateOp().Set(translation)

            # Create the point cloud geometry
            points = UsdGeom.Points.Define(stage, f'/PointCloud_{i}/Points')
            points.CreatePointsAttr(coordinates.tolist())
            points.CreateDisplayColorAttr(colors.tolist())
            
            print(f"Created point cloud {i} with {num_points} points at position {offsets[i]}.")

            # Store the references to remove them later
            self._created_point_clouds.append((f'/PointCloud_{i}', f'/PointCloud_{i}/Points'))

    def remove_point_clouds(self):
        """ Remove all created point clouds """
        stage = omni.usd.get_context().get_stage()
        
        # Iterate over the list of created point clouds and remove them
        for i, (xform_path, points_path) in enumerate(self._created_point_clouds):
            # Get the prims for xform and points using their paths
            xform_prim = stage.GetPrimAtPath(xform_path)
            points_prim = stage.GetPrimAtPath(points_path)
            
            # Remove the prims from the stage
            if xform_prim and points_prim:
                stage.RemovePrim(xform_prim.GetPath())
                stage.RemovePrim(points_prim.GetPath())
                print(f"Removed point cloud {i}.")

        # Clear the list after removal
        self._created_point_clouds.clear()
