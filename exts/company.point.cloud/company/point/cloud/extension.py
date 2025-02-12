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
        """ Create multiple point clouds evenly distributed within a 1.5 km x 1.5 km space """
        num_points = 1000  # Number of points per point cloud
        grid_size = 10  # Create a 10x10 grid of point clouds to cover the 1.5x1.5 km space

        # Distance between grid centers
        grid_spacing = 1500 / grid_size  # 1500 meters divided by grid size
        
        # Create the stage for USD
        stage = omni.usd.get_context().get_stage()

        # Generate grid of point cloud centers within the 1.5x1.5 km area
        for i in range(grid_size):
            for j in range(grid_size):
                # Calculate the position of each grid point (center of a point cloud)
                center_x = (i * grid_spacing) - 750  # Shift to center at 0,0
                center_y = (j * grid_spacing) - 750  # Shift to center at 0,0
                center_z = np.random.uniform(0, 100)  # Random Z height between 0 and 100 meters
                
                # Generate random coordinates for the points in this cloud around the center
                x = np.random.uniform(center_x - 25, center_x + 25, num_points)
                y = np.random.uniform(center_y - 25, center_y + 25, num_points)
                z = np.random.uniform(0, 100, num_points)  # Random heights between 0 and 100 meters
                coordinates = np.vstack([x, y, z]).T
                
                # Simulate gas concentration (values between 0 and 1)
                concentration = np.random.uniform(0, 1, num_points)
                
                # Color points based on concentration (blue to red scale)
                colors = np.stack([1 - concentration, np.zeros_like(concentration), concentration], axis=-1)

                # Define unique transform for this point cloud (position offset)
                xform = UsdGeom.Xform.Define(stage, f'/PointCloud_{i}_{j}')
                translation = Gf.Vec3f(center_x, center_y, center_z)
                xform.AddTranslateOp().Set(translation)

                # Create the point cloud geometry
                points = UsdGeom.Points.Define(stage, f'/PointCloud_{i}_{j}/Points')
                points.CreatePointsAttr(coordinates.tolist())
                points.CreateDisplayColorAttr(colors.tolist())
                
                print(f"Created point cloud at ({center_x}, {center_y}, {center_z}) with {num_points} points.")

                # Store the references to remove them later
                self._created_point_clouds.append((f'/PointCloud_{i}_{j}', f'/PointCloud_{i}_{j}/Points'))

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
