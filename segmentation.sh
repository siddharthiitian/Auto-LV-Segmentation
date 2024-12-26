    data_path='/Users/siddharth/Desktop/heart modeling/Auto_LV_Modeling/dataset/Ct test data'
    sv_python_dir='/Applications/SimVascular.app/Contents/MacOS'
    script_dir='/Applications/SimVascular.app/Contents/Resources/Python3.5/site-packages/sv_auto_lv_modeling'

    patient_id=WS01
    image_dir=$data_path/01-Images
    output_dir=$data_path/02-Segmnts
    weight_dir=$data_path/Weights

    ${sv_python_dir}/simvascular --python -- $script_dir/segmentation/prediction.py \
        --pid $patient_id \
        --image $image_dir \
        --output $output_dir \
        --model $weight_dir \
        --view  0 1 2 \ # 0 for axial, 1 for coronal, 2 for sagittal
        --modality ct # ct or mr



# from sv_auto_lv_modeling.auto_lv import Segmentation
# data_path='/path/to/WS01_data'
# seg = Segmentation()
# seg.set_modality('ct')
# seg.set_patient_id ('WS01')
# seg.set_image_directory (data_path+'/01-Images')
# seg.set_output_directory (data_path+'/02-Segmnts')
# seg.set_model_directory ([data_path+'/Weights'])
# seg.set_view ([2])
# seg.generate_segmentation()