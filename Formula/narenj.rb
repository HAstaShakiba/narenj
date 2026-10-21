# Homebrew formula. Install with:
#   brew tap hastashakiba/narenj https://github.com/HAstaShakiba/narenj
#   brew install narenj
# The release workflow updates url and sha256 for every tagged version.
class Narenj < Formula
  desc "Drag-and-drop ffmpeg wheel: convert, compress and trim files by dropping them"
  homepage "https://github.com/HAstaShakiba/narenj"
  url "https://github.com/HAstaShakiba/narenj/archive/refs/tags/v1.3.2.tar.gz"
  sha256 "e1a68820fabbc81e414d9caedf253d0559402e2ce8e2405890223e4af6995938"
  license "MIT"
  head "https://github.com/HAstaShakiba/narenj.git", branch: "main"

  depends_on "adwaita-icon-theme"
  depends_on "ffmpeg"
  depends_on "ghostscript"
  depends_on "gtk4"
  depends_on "libadwaita"
  depends_on "librsvg"
  depends_on "pandoc"
  depends_on "poppler"
  depends_on "py3cairo"
  depends_on "pygobject3"

  # the Python that pygobject3 is built for
  def python
    Formula["pygobject3"].deps.map(&:to_formula).select { |f| f.name.start_with?("python@") }.max_by(&:version)
  end

  def install
    libexec.install "narenj.py", "narenj.svg"
    libexec.install "icons" if File.directory?("icons") # shipped since 1.3.2
    (bin/"narenj").write <<~SH
      #!/bin/sh
      exec "#{python.opt_libexec}/bin/python" "#{libexec}/narenj.py" "$@"
    SH
  end

  def caveats
    <<~EOS
      Start Narenj with:  narenj
      Control+Option+N shows and hides the wheel while it runs.
      For Word, PowerPoint and Excel files, also install LibreOffice:  brew install --cask libreoffice
    EOS
  end

  test do
    # brew test has no window server, and even importing Gtk connects to it on macOS; check the
    # typelibs are there and load librsvg, which needs no display
    check = "import gi; [gi.require_version(n, v) for n, v in " \
            "(('Gtk', '4.0'), ('Adw', '1'), ('Rsvg', '2.0'))]; " \
            "from gi.repository import Rsvg; print('ok')"
    assert_equal "ok", shell_output("#{python.opt_libexec}/bin/python -c \"#{check}\"").strip
    assert_path_exists libexec/"narenj.py"
  end
end
