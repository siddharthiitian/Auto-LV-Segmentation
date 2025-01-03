import os
import numpy as np
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
import gc
import glob
import tensorflow as tf
from tensorflow.python.keras import models as models_keras
from tensorflow.python.keras import backend as K

import vtk
from pre_process import swap_labels_back, rescale_intensity, vtk_resample_to_size, vtk_resample_with_info_dict
from im_utils import load_vtk_image, write_vtk_image, get_array_from_vtkImage,get_vtkImage_from_array,vtk_write_mask_as_nifty
from model import UNet2D
import argparse
import time

def model_output_no_resize(model, im_vol, view, channel):
    im_vol = np.moveaxis(im_vol, view, 0)
    ipt = np.zeros([*im_vol.shape,channel])
    #shift array by channel num. If on boundary, fuse with
    #the slice on the other boundary
    shift = int((channel-1)/2)
    for i in range(channel):
        ipt[:,:,:,i] = np.roll(im_vol, shift-i, axis=0)
    start = time.time()
    prob = np.zeros(list(ipt.shape[:-1])+[model.layers[-1].output_shape[-1]])
    for i in range(prob.shape[0]):
        slice_im = np.expand_dims(ipt[i,:,:,:],axis=0)
        prob[i,:,:,:] = model.predict(slice_im)
    end = time.time()
    prob = np.moveaxis(prob, 0, view)
    return prob, end-start

def predict_volume(prob,labels):
    #im_vol, ori_shape, info = data_preprocess_test(image_vol_fn, view, 256, modality)
    predicted_label = np.argmax(prob, axis=-1)
    predicted_label = swap_labels_back(labels,predicted_label)
    return predicted_label

def dice_score(pred, true):
    pred = pred.astype(np.int)
    true = true.astype(np.int)  
    num_class = np.unique(true)
    
    #change to one hot
    dice_out = [None]*len(num_class)
    for i in range(1, len(num_class)):
        pred_c = pred == num_class[i]
        true_c = true == num_class[i]
        dice_out[i] = np.sum(pred_c*true_c)*2.0 / (np.sum(pred_c) + np.sum(true_c))
    
    mask =( pred > 0 )+ (true > 0)
    dice_out[0] = np.sum((pred==true)[mask]) * 2. / (np.sum(pred>0) + np.sum(true>0))
    return dice_out

class Prediction:
    #This is a class to get 3D volumetric prediction from the 2DUNet model
    def __init__(self, unet, model,modality,view,image_fn,label_fn, channel):
        self.unet=unet
        self.models=model
        self.modality=modality
        self.views=view
        self.image_fn = image_fn
        self.channel = channel
        self.label_fn = label_fn
        self.prediction = None
        self.dice_score = None
        self.original_shape = None
        assert len(self.models)==len(self.views), "Missing view attributes for models"
    def prepare_input_vtk(self, size):
        vtk_img = load_vtk_image(self.image_fn)
        self.image_info = {}
        self.image_info['spacing'] = vtk_img.GetSpacing()
        self.image_info['origin'] = vtk_img.GetOrigin()
        self.image_info['extent'] = vtk_img.GetExtent()
        self.image_info['size'] = vtk_img.GetDimensions()
        vtk_img = vtk_resample_to_size(vtk_img, (size, size, size))
        img_vol = get_array_from_vtkImage(vtk_img)
        img_vol = rescale_intensity(img_vol,self.modality, [750, -750])
        return img_vol
    def volume_prediction_average(self, size):

        img_vol = self.prepare_input_vtk(size)
        
        self.original_shape = img_vol.shape
        
        prob = np.zeros((*self.original_shape,8))
        unique_views = np.unique(self.views)
        
        self.pred_time = 0.
        for view in unique_views:
            indices = np.where(self.views==view)[0]
            predict_shape = [size,size,size,8]
            predict_shape[view] = img_vol.shape[view]
            prob_view = np.zeros(predict_shape)
            for i in indices:
                model_path = self.models[i]
                (self.unet).load_weights(model_path)
                p, t = model_output_no_resize(self.unet, img_vol, self.views[i], self.channel)
                prob_view += p
                self.pred_time += t
            prob += prob_view
        avg = prob/len(self.models)
        self.pred = predict_volume(avg, np.zeros(1))
        return 

    def dice(self):
        #assuming groud truth label has the same origin, spacing and orientation as input image
        label_vol = sitk.GetArrayFromImage(sitk.ReadImage(self.label_fn))
        pred_label = sitk.GetArrayFromImage(self.pred)
        pred_label = swap_labels_back(label_vol, pred_label)
        ds = dice_score(pred_label, label_vol)
        return ds
    
    def resample_prediction_vtk(self):
        im = get_vtkImage_from_array(self.pred.astype(np.uint8))
        self.pred = vtk_resample_with_info_dict(im, self.image_info, order=0)
        return 

    def write_prediction(self, out_fn):
        if not os.path.isdir(out_fn):
            try:
                os.makedirs(os.path.dirname(out_fn))
            except Exception as e: print(e)
        if out_fn[-4:] == '.vti' or out_fn[-4:] == '.mhd':
            write_vtk_image(self.pred, out_fn)
        elif out_fn[-4:] == '.nii' or out_fn[-7:] == '.nii.gz':
            vtk_write_mask_as_nifty(self.pred, self.image_fn, out_fn)
        else:
            raise IOError("Output file extension not supported: %s" % out_fn)
        return 


def seg_main(size, modality, patient_id, data_folder, data_out_folder, model_folder, view_attributes, channel):

    model_postfix = "small2"
    if model_folder is None :
        model_folder=[]
    else:
        model_folder=sorted(model_folder)
    model_folders = sorted(model_folder * len(view_attributes))
    view_attributes *= len(model_folder)

    names = ['axial', 'coronal', 'sagittal']
    view_names = [names[i] for i in view_attributes]
    if not os.path.isdir(data_out_folder):
        try:
            os.mkdir(data_out_folder)
        except Exception as e: print(e)
    
    #set up models
    img_shape = (size, size, channel)
    num_class = 8
    inputs, outputs = UNet2D(img_shape, num_class)
    unet = models_keras.Model(inputs=[inputs], outputs=[outputs])
    
    #load image filenames
    filenames = {}
    
    ext_list = ['.nii.gz', '.nii', '.vti']
    for m in modality:
        x_filenames = []
        for ext in ext_list:
            x_filenames += sorted(glob.glob(os.path.join(data_folder, patient_id, '*'+ext)))
        for i in range(len(x_filenames)):
            print("Processing "+x_filenames[i])            
            models = [os.path.join(mdl, 'weights_multi-all-%s_%s.hdf5' % (j, model_postfix)) for mdl, j in zip(model_folders, view_names)]
            predict = Prediction(unet, models,m,view_attributes,x_filenames[i], None, channel)
            predict.volume_prediction_average(size)
            predict.resample_prediction_vtk()
            predict.write_prediction(os.path.join(data_out_folder,patient_id,os.path.basename(x_filenames[i])))
    return 

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid',  help='Patient ID. If none, put None here.')
    parser.add_argument('--image',  help='Name of the folder containing the image data')
    parser.add_argument('--output',  help='Name of the output folder')
    parser.add_argument('--model', nargs='+',  help='Name of the folders containing the trained models')
    parser.add_argument('--view', type=int, nargs='+', help='List of views for single or ensemble prediction, split by space. For example, 0 1 2  axial(0), coronal(1), sagittal(2)')
    parser.add_argument('--modality', nargs='+', help='Name of the modality, mr, ct, split by space')
    parser.add_argument('--size', type=int,default=256, help='Size of images')
    parser.add_argument('--n_channel',type=int, default=1, help='Number of image channels of input')
    args = parser.parse_args()

    # if args.pid.lower() == "none":
    #     args.pid = ''
    
    seg_main(args.size, args.modality, args.pid, args.image, args.output, args.model, args.view, args.n_channel)
