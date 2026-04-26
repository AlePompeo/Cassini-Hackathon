%% AquaGuard: Sentinel-2 Pollution Index Maps
% Visualises MCI (Maximum Chlorophyll Index) and VNRI (VIS-NIR Reflectance
% Index) computed from a synthetic 200×200 Sentinel-2 scene containing:
%   - An oil slick region (high VNRI ≈ 0.30)
%   - An algal bloom region (high MCI ≈ 0.018)

clear; clc; close all;
rng(42);

N = 200;   % grid size

%% ─── Synthetic Sentinel-2 bands ───────────────────────────
% Background: clean sea water
B03 = 0.030 + 0.003 * randn(N, N);  % green  560 nm
B04 = 0.020 + 0.002 * randn(N, N);  % red    665 nm
B05 = 0.015 + 0.002 * randn(N, N);  % RE1    705 nm
B06 = 0.010 + 0.001 * randn(N, N);  % RE2    740 nm

% Oil slick: rows 20-90, cols 20-110 — high VNRI
B03(20:90, 20:110) = B03(20:90, 20:110) + 0.045 + 0.005*randn(71,91);
B06(20:90, 20:110) = B06(20:90, 20:110) + 0.030 + 0.004*randn(71,91);
B04(20:90, 20:110) = B04(20:90, 20:110) - 0.005;

% Algal bloom: rows 130-200, cols 120-190 — high MCI
B05(130:200, 120:190) = B05(130:200, 120:190) + 0.025 + 0.004*randn(71,71);
B04(130:200, 120:190) = B04(130:200, 120:190) + 0.005;
B06(130:200, 120:190) = B06(130:200, 120:190) + 0.010;

% Clip
B03 = max(0, min(1, B03));
B04 = max(0, min(1, B04));
B05 = max(0, min(1, B05));
B06 = max(0, min(1, B06));

%% ─── Index computation ─────────────────────────────────────
% MCI = r705 - r665 - (705-665)/(740-665) * (r740 - r665)
MCI = B05 - B04 - (40/75) * (B06 - B04);

% VNRI = -2 * (r560 - r665 - r740) / (r560 + r665 + r740)
num   = B03 - B04 - B06;
denom = B03 + B04 + B06;
VNRI  = -2 .* num ./ max(denom, 1e-6);

%% ─── RGB composite ─────────────────────────────────────────
R_ch = mat2gray(MCI,  [0, 0.03]);    % MCI in red channel
G_ch = mat2gray(VNRI, [0, 0.35]);   % VNRI in green channel
B_ch = mat2gray(B04,  [0, 0.08]);   % True-color blue

RGB = cat(3, R_ch, G_ch, B_ch);
RGB = max(0, min(1, RGB));

%% ─── Figure ─────────────────────────────────────────────────
fig = figure('Color', [0.04 0.08 0.16], 'Position', [50 50 1200 460]);

% Titles and axis style helper
styleAx = @(ax) set(ax, 'Color', [0.06 0.12 0.22], ...
                    'XColor', [0.7 0.85 1], 'YColor', [0.7 0.85 1], ...
                    'FontSize', 9);

%% Panel 1 — MCI map
ax1 = subplot(1, 3, 1, 'Parent', fig);
imagesc(ax1, MCI); axis(ax1, 'image');
colormap(ax1, hot(256));
cb1 = colorbar(ax1);
cb1.Color = [0.7 0.85 1];
title(ax1, 'MCI — Chlorophyll-a Index', 'Color', [0 0.85 1], 'FontSize', 11);
xlabel(ax1, 'Column (pixel)'); ylabel(ax1, 'Row (pixel)');
styleAx(ax1);
% Bloom annotation
annotation('textbox', [0.18 0.07 0.14 0.06], 'String', 'ALGAL BLOOM', ...
           'Color', [0 1 0.6], 'BackgroundColor', [0.04 0.08 0.16 0.8], ...
           'EdgeColor', [0 1 0.6], 'FontSize', 8, 'FontWeight', 'bold');

%% Panel 2 — VNRI map
ax2 = subplot(1, 3, 2, 'Parent', fig);
imagesc(ax2, VNRI); axis(ax2, 'image');
colormap(ax2, cool(256));
cb2 = colorbar(ax2);
cb2.Color = [0.7 0.85 1];
title(ax2, 'VNRI — Hydrocarbon Index', 'Color', [0 0.85 1], 'FontSize', 11);
xlabel(ax2, 'Column (pixel)');
styleAx(ax2);
% Oil annotation
annotation('textbox', [0.44 0.72 0.10 0.06], 'String', 'OIL SLICK', ...
           'Color', [1 0.5 0.1], 'BackgroundColor', [0.04 0.08 0.16 0.8], ...
           'EdgeColor', [1 0.5 0.1], 'FontSize', 8, 'FontWeight', 'bold');

%% Panel 3 — RGB composite
ax3 = subplot(1, 3, 3, 'Parent', fig);
imshow(RGB, 'Parent', ax3);
title(ax3, 'RGB Composite (R=MCI, G=VNRI, B=Red)', 'Color', [0 0.85 1], 'FontSize', 11);
xlabel(ax3, 'Column (pixel)');
styleAx(ax3);

%% Main title
sgtitle(fig, 'AquaGuard: Sentinel-2 Pollution Index Maps', ...
        'Color', [0 0.85 1], 'FontSize', 14, 'FontWeight', 'bold');

%% Summary stats
fprintf('\n=== Index Summary ===\n');
fprintf('MCI  max: %.4f  (bloom threshold: 0.005)\n', max(MCI(:)));
fprintf('VNRI max: %.4f  (oil threshold: 0.10)\n', max(VNRI(:)));
bloom_frac = mean(MCI(:) > 0.005);
oil_frac   = mean(VNRI(:) > 0.10);
fprintf('Bloom coverage: %.1f%%\n', bloom_frac * 100);
fprintf('Oil coverage:   %.1f%%\n', oil_frac * 100);

saveas(fig, 'sentinel2_indices.png');
fprintf('Saved: sentinel2_indices.png\n');
