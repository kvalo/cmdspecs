all
# The default style rejects ordered lists which are numbered 1, 2, 3.
rule 'MD029', :style => :ordered

# Keep a Changelog repeats the Added, Changed, ... headings under each
# version.
rule 'MD024', :allow_different_nesting => true

# Newer mdl flags link reference definitions whose URL is too long to
# fit. They can't be wrapped.
rule 'MD013', :treat_links_as_single_words => true
