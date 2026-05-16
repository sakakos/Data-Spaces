# Compile with lualatex for fontspec/system fonts
$pdflatex = 'lualatex -interaction=nonstopmode -synctex=1 %O %S';
$bibtex = 'biber %O %B';
$max_repeat = 5;