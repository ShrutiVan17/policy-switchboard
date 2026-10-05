"""Give decision tokens more influence than repeated JSON boilerplate."""
def make_verdict_loss(focus_ids,weight):
    import torch
    from torch.nn.functional import cross_entropy
    def loss(outputs,labels,num_items_in_batch=None):
        targets=labels[:,1:].contiguous()
        logits=outputs.logits[:,:-1,:].contiguous()
        errors=cross_entropy(logits.float().reshape(-1,logits.shape[-1]),targets.reshape(-1),ignore_index=-100,reduction='none').reshape(targets.shape)
        scales=(targets!=-100).float()
        focus=torch.zeros_like(targets,dtype=torch.bool)
        for identifier in focus_ids: focus |= targets==identifier
        scales=torch.where(focus,scales*weight,scales)
        return (errors*scales).sum()/scales.sum().clamp_min(1)
    return loss
