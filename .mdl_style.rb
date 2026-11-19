all
# The default style rejects ordered lists which are numbered 1, 2, 3.
rule 'MD029', :style => :ordered

# Keep a Changelog repeats the Added, Changed, ... headings under each
# version.
rule 'MD024', :allow_different_nesting => true
