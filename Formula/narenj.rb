# Homebrew formula. Install with:
#   brew tap hastashakiba/narenj https://github.com/HAstaShakiba/narenj
#   brew install narenj
# The release workflow updates url and sha256 for every tagged version.
class Narenj < Formula
  desc "Drag-and-drop ffmpeg wheel: convert, compress and trim files by dropping them"
  homepage "https://github.com/HAstaShakiba/narenj"
  url "https://github.com/HAstaShakiba/narenj/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "87e18bfa0c2e9c7445ada84c9a486b1fa9a1f0525396bafed5d8d9f74a46bbdd"
  license "MIT"
  head "https://github.com/HAstaShakiba/narenj.git", branch: "main"

  depends_on "adwaita-icon-theme"
  depends_on "ffmpeg"
  depends_on "gtk4"
  depends_on "libadwaita"
  depends_on "librsvg"
  depends_on "py3cairo"
  depends_on "pygobject3"

  # the Python that pygobject3 is built for
  def python
    Formula["pygobject3"].deps.map(&:to_formula).select { |f| f.name.start_with?("python@") }.max_by(&:version)
  end

  def install
    libexec.install "narenj.py", "narenj.svg"
    (bin/"narenj").write <<~SH
      #!/bin/sh
      exec "#{python.opt_libexec}/bin/python" "#{libexec}/narenj.py" "$@"
    SH
  end

  def caveats
    <<~EOS
      Start Narenj with:  narenj
      Control+Option+N shows and hides the wheel while it runs.
    EOS
  end

  test do
    assert_match "--toggle", shell_output("#{bin}/narenj --help")
  end
end
