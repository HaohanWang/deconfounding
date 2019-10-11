# Deconfounding Key-word Statistics 

## Usage
```python generate.py [num-to-gen] [ngram] [--rebuild]```

##### example: 
```python generate.py 1000 3 --rebuild```


## Key variables
- `word_dict`: mapping from word(str) to word index(int) in the vocabulary
- `effect_list`: mapping from word index(int) to word effect(float) 
- `ngrams`: mapping from an ngram window(a tuple of strings) to a probability
- `samples`: a list of samples, each having the following fields:
    * `sentence`: the sentence as a list of strings
    * `effect`: a list of float as effect for each word in the sentence
    * `bow_repr`: bag-of-word representation of the sentence (sum of each word as one-hot vectors)
    * `label`: 0 for negative, 1 for positive

## TODO:
- Words / trigrams that never appeared should be assigned a better possibility.
- Word effects should be calculated in a better way

