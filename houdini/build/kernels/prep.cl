// prep: the grey analysis image. grey = max(dot(rgb, weights) * gain, 0) ^ (1 / gamma), written to R, G and B.
// Alpha is ignored. Nothing clamps at 1: the worker quantises with rint(x * 255) and records the clipped share.
// weights, gain and gamma are Bindings multiparm entries driven by the asset's Analysis controls.
#bind layer src float4
#bind layer !&grey float3
@KERNEL
{
    float4 c = @src;
    float l = fmax((c.x * @weights.x + c.y * @weights.y + c.z * @weights.z) * @gain, 0.0f);
    if (@gamma != 1.0f)
        l = pow(l, 1.0f / @gamma);
    @grey.set((float3)(l, l, l));
}
