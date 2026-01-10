{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.chromium
    pkgs.chromedriver
    pkgs.xvfb-run
  ];
  env = {
    CHROME_BIN = "${pkgs.chromium}/bin/chromium";
  };
}
