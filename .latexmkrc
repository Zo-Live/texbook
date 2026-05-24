use Cwd qw(abs_path getcwd);
use File::Basename qw(dirname);
use File::Spec;

my $cwd = abs_path(getcwd());
my $repo_root = (-d "$cwd/src" && -d "$cwd/src/texbook")
    ? $cwd
    : (-d "$cwd/../src" && -d "$cwd/../src/texbook")
        ? abs_path("$cwd/..")
        : $cwd;
my $post_build = "$repo_root/scripts/post-build.sh";
my $src_root = "$repo_root/src";

sub _texbook_unquote_arg {
    my ($value) = @_;
    $value =~ s/^"(.*)"$/$1/;
    $value =~ s/^'(.*)'$/$1/;
    return $value;
}

sub _texbook_first_tex_arg {
    for (my $i = 0; $i <= $#ARGV; $i++) {
        my $arg = _texbook_unquote_arg($ARGV[$i]);
        if ($arg =~ /^-/) {
            $i++ if $arg =~ /^--?(?:r|e|aux-directory|auxdir|output-directory|outdir|jobname|pdfxelatex|xelatex|pdflatex|lualatex|latex|MF|deps-out)$/;
            next;
        }
        return $arg if $arg =~ /\.tex$/i;
        return "$arg.tex" if $arg ne '';
    }
    return '';
}

sub _texbook_shell_quote {
    my ($value) = @_;
    $value =~ s/'/'"'"'/g;
    return "'$value'";
}

sub _texbook_mirror_parent {
    my ($tex_arg) = @_;
    return '' if $tex_arg eq '';

    my $path = File::Spec->file_name_is_absolute($tex_arg)
        ? $tex_arg
        : File::Spec->rel2abs($tex_arg, $cwd);
    my $tex_dir = dirname($path);
    return '' if ! -d $tex_dir;

    my $abs_dir = abs_path($tex_dir);
    return '' if ! defined $abs_dir;
    my $relative = File::Spec->abs2rel($abs_dir, $src_root);
    return '' if $relative eq '.';
    return '' if $relative =~ /^\.\.(?:\/|$)/;
    return $relative;
}

my $texbook_tex_arg = _texbook_first_tex_arg();
my $texbook_mirror_parent = _texbook_mirror_parent($texbook_tex_arg);

$pdf_mode = 5;
$do_cd = 1;
$emulate_aux = 1;

$out_dir = $texbook_mirror_parent eq ''
    ? "$repo_root/out"
    : "$repo_root/out/$texbook_mirror_parent";
$aux_dir = $texbook_mirror_parent eq ''
    ? "$repo_root/build"
    : "$repo_root/build/$texbook_mirror_parent";

$xelatex = 'xelatex -synctex=1 -interaction=nonstopmode -file-line-error %O %S';

if (-f $post_build) {
    my $post_build_cmd = join(
        ' ',
        'bash',
        _texbook_shell_quote($post_build),
        _texbook_shell_quote($repo_root),
        '%R',
        '%V',
        '%W',
        '%T',
    );
    $success_cmd = $post_build_cmd;
    $warning_cmd = $success_cmd;
}

$clean_ext = 'aux bbl blg log out nav snm toc synctex synctex.gz fls fdb_latexmk xdv thm lol lot lof';
