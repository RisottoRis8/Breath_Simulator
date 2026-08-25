%% Script Completo: Metadati + Confronto Interpolazioni Multiple
clear; clc; close all;

% --- PARAMETRI DI CONFIGURAZIONE ---
% Scegli i metodi da confrontare
metodi = {'linear', 'pchip', 'spline', 'makima'}; 
n_factor = 8; % Moltiplicatore punti (n * num_samples)

% --- SELEZIONE FILE ---
[file, path] = uigetfile('*.csv', 'Seleziona il file di misura CSV');
if isequal(file, 0), return; end
filename = fullfile(path, file);

% --- 1. ESTRAZIONE E STAMPA METADATI A TERMINALE ---
fid = fopen(filename, 'r');
fprintf('\n==========================================\n');
fprintf('   RIEPILOGO METADATI: %s\n', file);
fprintf('==========================================\n');

for i = 1:5
    linea = fgetl(fid);
    if i > 1 % Saltiamo la riga del titolo generico "--- RIEPILOGO... ---"
        % Sostituiamo la virgola con ": " per una lettura pulita
        info_pulita = strrep(linea, ',', ': ');
        fprintf('  > %s\n', info_pulita);
    end
end
fclose(fid);
fprintf('==========================================\n\n');

% --- 2. CARICAMENTO DATI TABELLARI ---
opts = detectImportOptions(filename);
opts.VariableNamingRule = 'preserve';
opts.DataLine = 8;          % I dati numerici iniziano alla riga 8
opts.VariableNamesLine = 7; % Intestazioni alla riga 7

data = readtable(filename, opts);
t_orig = data.Time_s;
p_orig = data.Pressure_Pa;

% Pulizia dati (rimozione duplicati temporali obbligatoria per interp1)
[t, idx] = unique(t_orig);
p = p_orig(idx);

% --- 3. CALCOLO PUNTI E VETTORE TEMPO ---
num_samples = length(t);
num_punti_interp = n_factor * num_samples;
t_interp = linspace(min(t), max(t), num_punti_interp);

% --- 4. GENERAZIONE GRAFICO ---
figure('Color', 'w', 'Name', ['Confronto Metodi: ' file], 'Position', [100, 100, 1100, 700]);
hold on;

% Plottiamo i dati originali
plot(t, p, 'ko', 'MarkerFaceColor', [0.4 0.4 0.4], 'MarkerSize', 4, ...
    'DisplayName', sprintf('Dati Originali (%d pts)', num_samples));

% Ciclo per ogni metodo di interpolazione
colori = lines(length(metodi)); % Mappa colori automatica

for i = 1:length(metodi)
    metodo_attuale = metodi{i};
    
    % Calcolo interpolazione
    p_interp = interp1(t, p, t_interp, metodo_attuale);
    
    % Plot della curva
    plot(t_interp, p_interp, 'LineWidth', 1.8, 'Color', colori(i,:), ...
        'DisplayName', ['Metodo: ' metodo_attuale]);
end

% --- ABBELLIMENTO GRAFICO ---
grid on; box on;
xlabel('Tempo (s)', 'FontSize', 11);
ylabel('Pressione (Pa)', 'FontSize', 11);
title({['Analisi File: ' file], ...
       sprintf('Risoluzione aumentata: %d punti (Fattore n=%d)', num_punti_interp, n_factor)}, ...
       'FontSize', 13);

legend('Location', 'northeastoutside', 'FontSize', 10);
axis tight; 

% Feedback finale a terminale
fprintf('Elaborazione completata:\n');
fprintf('- Numero campioni originali: %d\n', num_samples);
fprintf('- Numero punti calcolati: %d\n', num_punti_interp);
fprintf('- Metodi visualizzati: %s\n\n', strjoin(metodi, ', '));