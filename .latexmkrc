use Cwd qw(abs_path getcwd);

my $cwd = abs_path(getcwd());
my $repo_root = (-d "$cwd/src" && -d "$cwd/src/texbook")
    ? $cwd
    : (-d "$cwd/../src" && -d "$cwd/../src/texbook")
        ? abs_path("$cwd/..")
        : $cwd;
my $post_build = "$repo_root/scripts/post-build.sh";

$pdf_mode = 5;
$do_cd = 1;
$emulate_aux = 1;

$out_dir = "$repo_root/out";
$aux_dir = "$repo_root/build";

$xelatex = 'xelatex -synctex=1 -interaction=nonstopmode -file-line-error %O %S';

if (-f $post_build) {
    $success_cmd = "bash \"$post_build\" \"$repo_root\"";
    $warning_cmd = $success_cmd;
}

$clean_ext = 'aux bbl blg log out nav snm toc synctex synctex.gz fls fdb_latexmk xdv thm lol lot lof';
