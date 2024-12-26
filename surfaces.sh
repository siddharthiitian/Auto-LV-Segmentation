# Use SimVascular to construct LV surface meshes

# Path to SimVascular exectuable
sv_python_dir=/Applications/SimVascular.app/Contents/MacOS
model_script=modeling/surface_main.py
# Path to the segmentation results
input_dir=./SB3C_test_sa/WS01
# Path to the outputed surface meshes
output_dir=./SB3C_test_sa_surf/WS01

# Construct LV surface meshes with tagged boundary faces
for file in ${input_dir}/*.nii.gz
do 
    echo ${file}
    ${sv_python_dir}/SimVascular --python \
        -- ${model_script} \
        --input_dir ${input_dir} \
        --output_dir ${output_dir} \
        --seg_name ${file##*/} \
        --edge_size 3.5
done
