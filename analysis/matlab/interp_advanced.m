%% Script: Interpolazione, Media e Trend Robusto (LOESS)
clear; clc; close all;

% --- PARAMETRI DI CONFIGURAZIONE ---
metodo_interp = 'pchip'; 
n_factor = 8;
% Parametro di smoothing: tra 0 e 1. 
% Più è alto, più la curva sarà "morbida" e ignorerà le variazioni rapide.
span_smoothing = 0.15; 

% --- SELEZIONE FILE ---
[file, path] = uigetfile('*.csv', 'Seleziona il file di misura CSV');
if isequal(file, 0), return; end
filename = fullfile(path, file);

% --- 1. ESTRAZIONE METADATI E MEDIA ---
meta_cells = readcell(filename, 'Range', 'A1:B6');
p_media_val = NaN;
for r = 1:size(meta_cells, 1)
    label = string(meta_cells{r,1});
    if contains(label, 'Pressione Media', 'IgnoreCase', true)
        valore = meta_cells{r,2};
        p_media_val = ifischar(valore, str2double(valore), valore);
        break;
    end
end

% --- 2. CARICAMENTO DATI ---
opts = detectImportOptions(filename);
opts.DataLine = 8; 
opts.VariableNamesLine = 7;
data = readtable(filename, opts);
t = data.Time_s;
p = data.Pressure_Pa;
[t, idx] = unique(t); p = p(idx);

% --- 3. CALCOLO CURVE ---
% A. Interpolazione Standard (segue tutti i punti)
num_punti_interp = n_factor * length(t);
t_interp = linspace(min(t), max(t), num_punti_interp);
p_interp = interp1(t, p, t_interp, metodo_interp);

% B. Curva di Trend Robusta (Lowess)
% Usiamo smoothdata per calcolare il trend che ignora i picchi
p_smooth = smoothdata(p, 'rlowess', 'SmoothingFactor', span_smoothing);
% Interpoliamo il trend per averlo fluido sul grafico
p_smooth_interp = interp1(t, p_smooth, t_interp, 'pchip');

% --- 4. VISUALIZZAZIONE ---
figure('Color', 'w', 'Position', [100, 100, 1100, 700]);
hold on;

% Dati originali
plot(t, p, 'ko', 'MarkerFaceColor', [0.8 0.8 0.8], 'MarkerSize', 3, ...
    'DisplayName', 'Dati Sperimentali (Grezzi)');

% Interpolazione Standard
plot(t_interp, p_interp, 'Color', [0.6 0.6 0.6], 'LineWidth', 0.5, ...
    'DisplayName', ['Interpolazione ' metodo_interp]);

% Linea Pressione Media
if ~isnan(p_media_val)
    yline(p_media_val, '--r', 'LineWidth', 1.5, ...
        'DisplayName', sprintf('Pressione Media (%.2f Pa)', p_media_val));
end

% Curva di Trend Robusta (rlowess)
plot(t_interp, p_smooth_interp, 'b-', 'LineWidth', 2.5, ...
    'DisplayName', 'Trend Robusto (Ignora variazioni rapide)');

% Abbellimenti
grid on; box on;
xlabel('Tempo (s)'); ylabel('Pressione (Pa)');
title({['Analisi Avanzata: ' file], ...
       ['Smoothing Factor: ' num2str(span_smoothing) ' (Robust LOESS)']});
legend('Location', 'northeastoutside');
axis tight;

% --- FUNZIONE DI SUPPORTO ---
function out = ifischar(val, ifTrue, ifFalse)
    if ischar(val) || isstring(val), out = ifTrue; else, out = ifFalse; end
end