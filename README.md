# NERDA-Con <img src="https://raw.githubusercontent.com/SupritiVijay/NERDA-Con/main/logo.png" align="right" height=350/>

Extending NERDA Library for Continual Learning

## Installation Guide

`pip install NERDA-Con`

Due to a recent issue with `scikit-learn` installation, which is an ongoing issue with the original NERDA, we have fixed it on the GitHub repository, and you can install the updated version as follows:

`pip install nerda-con@git+https://github.com/SupritiVijay/nerda-con`

## Implementation and Execution

### Training

`model.train_next_task(training,validation)`

The `training` and `validation` must be NERDA-optimized dataloaders.

### Evaluation

`model.evaluate_performance(test)`

### Shared Model

To set shared model parameters, 

`model.shared_model = model.transformer_model`

## Cite This Work

```
@inproceedings{nerda-con,
  title = {NERDA-Con},
  author = {Supriti Vijay, Aman Priyanshu},
  year = {2022},
  publisher = {{GitHub}},
  url = {https://github.com/SupritiVijay/NERDA-Con}
}

``` 

## References

### NERDA

[Nerda](https://github.com/ebanalyse/NERDA) is a framework for fine-tuning pretrained transformers for Named-Entity Recognition (NER) tasks.
```
@inproceedings{nerda,
  title = {NERDA},
  author = {Kjeldgaard, Lars and Nielsen, Lukas},
  year = {2021},
  publisher = {{GitHub}},
  url = {https://github.com/ebanalyse/NERDA}
}
```
