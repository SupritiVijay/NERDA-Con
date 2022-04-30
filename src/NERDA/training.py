import numpy as np
from .preprocessing import create_dataloader
from sklearn import preprocessing
from transformers import AdamW, get_linear_schedule_with_warmup
import random
import torch
from IPython import get_ipython

def isnotebook():
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            from tqdm.notebook import tqdm   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            from tqdm import tqdm # Terminal running IPython
        else:
            from tqdm import tqdm  # Other type (?)
    except NameError:
        from tqdm import tqdm 
        
isnotebook()

def train(model, data_loader, optimizer, device, scheduler, n_tags):
    """One Iteration of Training"""

    model.train()    
    final_loss = 0.0
    
    for dl in tqdm(data_loader, total=len(data_loader)):

        optimizer.zero_grad()
        outputs = model(**dl)
        loss = compute_loss(outputs, 
                            dl.get('target_tags'),
                            dl.get('masks'), 
                            device, 
                            n_tags)
        loss.backward()
        optimizer.step()
        scheduler.step()
        final_loss += loss.item()

    # Return average loss
    return final_loss / len(data_loader)

def validate(model, data_loader, device, n_tags):
    """One Iteration of Validation"""

    model.eval()
    final_loss = 0.0

    for dl in tqdm(data_loader, total=len(data_loader)):
        
        outputs = model(**dl)
        loss = compute_loss(outputs, 
                            dl.get('target_tags'),
                            dl.get('masks'), 
                            device, 
                            n_tags)
        final_loss += loss.item()
    
    # Return average loss.
    return final_loss / len(data_loader)   

def compute_loss(preds, target_tags, masks, device, n_tags):
    
    # initialize loss function.
    lfn = torch.nn.CrossEntropyLoss()

    # Compute active loss to not compute loss of paddings
    active_loss = masks.view(-1) == 1

    active_logits = preds.view(-1, n_tags)
    active_labels = torch.where(
        active_loss,
        target_tags.view(-1),
        torch.tensor(lfn.ignore_index).type_as(target_tags)
    )

    active_labels = torch.as_tensor(active_labels, device = torch.device(device), dtype = torch.long)
    
    # Only compute loss on actual token predictions
    loss = lfn(active_logits, active_labels)

    return loss

def enforce_reproducibility(seed = 42) -> None:
    """Enforce Reproducibity

    Enforces reproducibility of models to the furthest 
    possible extent. This is done by setting fixed seeds for
    random number generation etcetera. 

    For atomic operations there is currently no simple way to
    enforce determinism, as the order of parallel operations
    is not known.

    Args:
        seed (int, optional): Fixed seed. Defaults to 42.  
    """
    # Sets seed manually for both CPU and CUDA
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    # CUDNN
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    # System based
    random.seed(seed)
    np.random.seed(seed)

def train_model(network,
                tag_encoder,
                tag_outside,
                transformer_tokenizer,
                transformer_config,
                dataset_training, 
                dataset_validation, 
                max_len = 128,
                train_batch_size = 16,
                validation_batch_size = 8,
                epochs = 5,
                warmup_steps = 0,
                learning_rate = 5e-5,
                device = None,
                fixed_seed = 42,
                num_workers = 1):
    
    if fixed_seed is not None:
        enforce_reproducibility(fixed_seed)
    
    # compute number of unique tags from encoder.
    n_tags = tag_encoder.classes_.shape[0]

    # prepare datasets for modelling by creating data readers and loaders
    dl_train = create_dataloader(sentences = dataset_training.get('sentences'),
                                 tags = dataset_training.get('tags'), 
                                 transformer_tokenizer = transformer_tokenizer, 
                                 transformer_config = transformer_config,
                                 max_len = max_len, 
                                 batch_size = train_batch_size, 
                                 tag_encoder = tag_encoder,
                                 tag_outside = tag_outside,
                                 num_workers = num_workers)
    dl_validate = create_dataloader(sentences = dataset_validation.get('sentences'), 
                                    tags = dataset_validation.get('tags'),
                                    transformer_tokenizer = transformer_tokenizer,
                                    transformer_config = transformer_config, 
                                    max_len = max_len, 
                                    batch_size = validation_batch_size, 
                                    tag_encoder = tag_encoder,
                                    tag_outside = tag_outside,
                                    num_workers = num_workers)

    optimizer_parameters = network.parameters()

    num_train_steps = int(len(dataset_training.get('sentences')) / train_batch_size * epochs)
    
    optimizer = AdamW(optimizer_parameters, lr = learning_rate)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps = warmup_steps, num_training_steps = num_train_steps
    )

    train_losses = []
    best_valid_loss = np.inf

    for epoch in range(epochs):
        
        print('\n Epoch {:} / {:}'.format(epoch + 1, epochs))

        train_loss = train(network, dl_train, optimizer, device, scheduler, n_tags)
        train_losses.append(train_loss)
        valid_loss = validate(network, dl_validate, device, n_tags)

        print(f"Train Loss = {train_loss} Valid Loss = {valid_loss}")

        if valid_loss < best_valid_loss:
            best_parameters = network.state_dict()            
            best_valid_loss = valid_loss

    # return best model
    network.load_state_dict(best_parameters)

    return network, train_losses, best_valid_loss

def on_task_update(task_id,fisher_dict,opt_param_dict, model, data_loader, optimizer, device, scheduler, n_tags, shared_model):
    model.train()
    optimizer.zero_grad()
    
    for dl in tqdm(data_loader, total=len(data_loader), desc='Computing Fisher Score and optimal parameters'):
        outputs = model(**dl)
        loss = compute_loss(outputs, 
                            dl.get('target_tags'),
                            dl.get('masks'), 
                            device, 
                            n_tags)
        loss.backward()
    
    fisher_dict[task_id] = {}
    opt_param_dict[task_id] = {}
    
    for name,param in shared_model.named_parameters():
        opt_param_dict[task_id][name] = param.data.clone()
        fisher_dict[task_id][name] = param.grad.data.clone().pow(2)
    
def train_ewc(task_id,fisher_dict,opt_param_dict, model, data_loader, optimizer, device, scheduler, n_tags, shared_model, ewc_lambda):
    
    model.train()    
    final_loss = 0.0
    
    for dl in tqdm(data_loader, total=len(data_loader)):

        optimizer.zero_grad()
        outputs = model(**dl)
        loss = compute_loss(outputs, 
                            dl.get('target_tags'),
                            dl.get('masks'), 
                            device, 
                            n_tags)
        for task in range(task_id):
            for name,param in shared_model.named_parameters():
                fisher = fisher_dict[task][name]
                opt_param = opt_param_dict[task][name]
                loss += (fisher * (opt_param - param).pow(2)).sum() *ewc_lambda
                    
            
        loss.backward()
        optimizer.step()
        scheduler.step()
        final_loss += loss.item()

    # Return average loss
    return final_loss / len(data_loader)

def train_model_new_task(network,
                tag_encoder,
                tag_outside,
                transformer_tokenizer,
                transformer_config,
                dataset_training, 
                dataset_validation, 
                max_len = 128,
                train_batch_size = 16,
                validation_batch_size = 8,
                epochs = 5,
                warmup_steps = 0,
                learning_rate = 5e-5,
                device = None,
                fixed_seed = 42,
                num_workers = 1,
                task_id = 0,
                fisher_dict = {},
                opt_param_dict = {},
                shared_model = None,
                ewc_lambda = 0.2):
    
    if fixed_seed is not None:
        enforce_reproducibility(fixed_seed)
        
    if shared_model is None:
        shared_model = network
    
    # compute number of unique tags from encoder.
    n_tags = tag_encoder.classes_.shape[0]

    # prepare datasets for modelling by creating data readers and loaders
    dl_train = create_dataloader(sentences = dataset_training.get('sentences'),
                                 tags = dataset_training.get('tags'), 
                                 transformer_tokenizer = transformer_tokenizer, 
                                 transformer_config = transformer_config,
                                 max_len = max_len, 
                                 batch_size = train_batch_size, 
                                 tag_encoder = tag_encoder,
                                 tag_outside = tag_outside,
                                 num_workers = num_workers)
    dl_validate = create_dataloader(sentences = dataset_validation.get('sentences'), 
                                    tags = dataset_validation.get('tags'),
                                    transformer_tokenizer = transformer_tokenizer,
                                    transformer_config = transformer_config, 
                                    max_len = max_len, 
                                    batch_size = validation_batch_size, 
                                    tag_encoder = tag_encoder,
                                    tag_outside = tag_outside,
                                    num_workers = num_workers)

    optimizer_parameters = network.parameters()

    num_train_steps = int(len(dataset_training.get('sentences')) / train_batch_size * epochs)
    
    optimizer = AdamW(optimizer_parameters, lr = learning_rate)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps = warmup_steps, num_training_steps = num_train_steps
    )

    train_losses = []
    best_valid_loss = np.inf

    for epoch in range(epochs):
        
        print('\n Epoch {:} / {:}'.format(epoch + 1, epochs))

        train_loss = train_ewc(task_id,fisher_dict,opt_param_dict, network, dl_train, optimizer, device, scheduler, n_tags, shared_model, ewc_lambda)
        train_losses.append(train_loss)
        valid_loss = validate(network, dl_validate, device, n_tags)

        print(f"Train Loss = {train_loss} Valid Loss = {valid_loss}")

        if valid_loss < best_valid_loss:
            best_parameters = network.state_dict()            
            best_valid_loss = valid_loss
    
    on_task_update(task_id,fisher_dict,opt_param_dict, network, dl_train, optimizer, device, scheduler, n_tags, shared_model)
    # return best model
    # network.load_state_dict(best_parameters)

    return network, train_losses, best_valid_loss


        
