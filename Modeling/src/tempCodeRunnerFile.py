    import os
    import sys
    import numpy as np
    import glob
    import SimpleITK as sitk
    import vtk
    import io_utils
    import utils
    from image_processing import LVImage
    import models
    class Registration:
        """
        Class to perform 3D image registration
        """
        def __init__(self, fixed_im_fn=None, moving_im_fn=None, fixed_mask_fn=None):
            """

            Args:
                fixed_im_fn: target image fn
                moving_im_fn: moving image fn
            """
            self.fixed_fn = fixed_im_fn
            self.moving_fn = fixed_im_fn
            self.fixed = None
            self.moving = None
            self.fixed_mask_fn = fixed_mask_fn
        #    self.moving_mask_fn = moving_mask_fn
            self.fixed_mask = None
        #    self.moving_mask = None
            self.parameter_map = None

        def update_moving_image(self, moving_im_fn):
            self.moving_fn = moving_im_fn
            self.moving = None
            self.parameter_map = None

        def update_fixed_image(self, fixed_im_fn):
            self.fixed_fn = fixed_im_fn
            self.fixed = None
            self.parameter_map = None
        
        #def updateMovingMask(self, moving_mask_fn):
        #    self.moving_mask_fn = moving_mask_fn
        #    self.moving_mask = None
        #    self.parameter_map = None

        def update_fixed_mask(self, fixed_mask_fn):
            self.fixed_mask_fn = fixed_mask_fn
            self.fixed_mask = None
            self.parameter_map = None
        @staticmethod
        def process_images(image):
            FACTOR_LA = 18 # TO-DO: change to global variables
            FACTOR_AA = 38
            lv_image = LVImage(image)
            lv_image.process([1, 4, 5, 7])
            la_cutter, la_nrm = lv_image.build_cutter(2, 6, 3, FACTOR_LA, op='valve')
            aa_cutter, aa_nrm = lv_image.build_cutter(6, 2, 3, FACTOR_AA, op='tissue')
            lv_label = utils.recolor_vtk_image_by_polydata(la_cutter, lv_image.label, 0)
            lv_label = utils.recolor_vtk_image_by_polydata(aa_cutter, lv_label,0)
            sitk_image = io_utils.vtk_image_to_sitk_image(lv_label)
            #sitk_image = sitk.ReadImage(image)
            res = np.array(sitk_image.GetSpacing())
            res = np.min(res)/res * 0.8
            sitk_image = utils.resample(sitk_image, res, order=0)
            sitk_image = utils.normalize_label_map(sitk_image, values=[100,110,120,130], keep=[1, 2, 3, 6])
            return sitk_image
        
        def load_images(self):
            self.moving = self.process_images(self.moving_fn)
            if self.fixed is None:
                self.fixed = self.process_images(self.fixed_fn)
        
        def compute_transform(self):

            if (self.fixed is None) or (self.moving is None):
                self.load_images()
            elastixImageFilter = sitk.ElastixImageFilter()
            elastixImageFilter.SetFixedImage(self.fixed)
            #elastixImageFilter.SetFixedMask(self.fixed_mask)
            p_map_1 = sitk.GetDefaultParameterMap('translation')
            p_map_2 = sitk.GetDefaultParameterMap('affine')
            p_map_3 = sitk.GetDefaultParameterMap('bspline')
            p_map_3['Registration'] = ['MultiResolutionRegistration']
            p_map_3['Metric'] = ['AdvancedMeanSquares']
            p_map_3['MaximumNumberOfIterations'] = ['256']
            p_map_3['FinalGridSpacingInPhysicalUnits'] = []
            p_map_3["MaximumNumberOfSamplingAttempts"] = ['4']
            p_map_3["FinalGridSpacingInVoxels"] = ['18']
            p_map_3['FinalBSplineInterpolationOrder'] = ['2']
            sitk.PrintParameterMap(p_map_3)
            elastixImageFilter.SetParameterMap(p_map_1)
            elastixImageFilter.AddParameterMap(p_map_2)
            elastixImageFilter.AddParameterMap(p_map_3)
            elastixImageFilter.SetMovingImage(self.moving)
            #elastixImageFilter.SetMovingMask(self.moving_mask)
            elastixImageFilter.Execute()

            self.parameter_map = elastixImageFilter.GetTransformParameterMap()

        def write_parameter_map(self, fn):
            if self.parameter_map is None:
                return
            for i, para_map in enumerate(self.parameter_map):
                para_map_fn = os.path.splitext(fn)[0]+'_%d.txt' % i
                sitk.WriteParameterFile(para_map, para_map_fn)

        def read_parameter_map(self, fn):
            fns = sorted(glob.glob(os.path.splitext(fn)[0]+"*"))
            if len(fns)==0:
                raise IOError("No Transformation file found")
            map_list = list()
            for para_map_fn in fns:
                map_list.append(sitk.ReadParameterFile(para_map_fn))
            self.parameter_map=tuple(map_list)
        def polydata_image_transform(self, model, fn, fn_paras=None):
            """
            Transform the points of a geometry using the computed transformation
            
            Args:
                poly: surface mesh to transform (vtk PolyData)
                fn: file name to write the vertices of polydata to file
                fn_paras: file name to the parameter map of previously done registration
            Returns:
                new_poly: transformed surface mesh (vtk PolyData)
            """

            io_utils.write_vtk_polydataVerts(model.poly, fn)
            if self.parameter_map is None:
                try:
                    self.read_parameter_map(fn_paras)
                except Exception as e:
                    self.compute_transform()
            if (self.fixed is None) or (self.moving is None):
                self.load_images()

            # wrap point set
            transformixImageFilter = sitk.TransformixImageFilter()
            transformixImageFilter.SetMovingImage(self.moving)
            transformixImageFilter.SetTransformParameterMap(self.parameter_map)
            transformixImageFilter.SetFixedPointSetFileName(fn)
            transformixImageFilter.SetOutputDirectory(os.path.dirname(fn))
            transformixImageFilter.Execute()
            # build VTK PolyData
            pts = io_utils.read_elastix_point_ouptut(os.path.join(os.path.dirname(fn),'outputpoints.txt'))

            new_poly = vtk.vtkPolyData()
            new_poly.DeepCopy(model.poly)
            new_poly.SetPoints(pts)
            return models.LeftVentricle(model.update(new_poly), model.edge_size)


            

