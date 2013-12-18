NAME = 'reco.conf'

TEMPLATE = """[general]
{disable}axis = {axis}
{disable}angle_step = {angle}
{disable}input = {input}
{disable}output = {output}

## Reconstruct from projections instead of sinograms
{disable_fp}from_projections = {from_projections}
## Flat-field correction will not be performed if these are missing
#darks = path/to/darks
#flats = path/to/flats

[fbp]
# crop_width = 128

[dfi]
# oversampling = 2
"""


def write(axis=0.0, angle=0.0, disable='#',
          input='path/to/input', output='path/to/output',
          from_projections=True):
    disable_fp = '#' if not from_projections else ''
    out = TEMPLATE.format(axis=axis, angle=angle, input=input,
                          output=output, from_projections=from_projections,
                          disable=disable, disable_fp=disable_fp)

    with open(NAME, 'w') as f:
        f.write(out)
