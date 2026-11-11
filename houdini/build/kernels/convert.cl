// convert: the one node that changes the flow's units, sign and size (CLAUDE.md, contract v1).
// flowexr holds the worker's flow.####.exr at analysis size: R = u, G = v in opencv_px (x right, y down), B = valid.
// Houdini's image space is half the longer side per unit with v up (FACTS P4, tests/thresholds/houdini_units.json),
// so u = R / (max(xres, yres) / 2) and v = -G / (max(xres, yres) / 2), measured on the analysis image; the analysis
// scale cancels because the output keeps the source's image space. Flow is sampled bilinearly at @P with the border
// clamped; valid is the nearest analysis pixel's B, thresholded at 0.5. Outputs take their size from source.
#bind layer flowexr float3 border=CLAMP
#bind layer source float4
#bind layer !&flow float2
#bind layer !&valid float
@KERNEL
{
    float half_long = 0.5f * (float)max(@flowexr.xres, @flowexr.yres);
    float3 f = @flowexr.imageSample(@P);
    float3 n = @flowexr.imageNearest(@P);
    @flow.set((float2)(f.x / half_long, -f.y / half_long));
    @valid.set(n.z >= 0.5f ? 1.0f : 0.0f);
}
